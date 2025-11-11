import logging
import calendar
from datetime import datetime, timedelta, date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timezone import make_aware, make_naive

from rest_framework import generics, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.choices import EventDateMode
from .models import (
    CompletionStatus, Event, EventInstance, Slot,
    SchedulePattern, MonthSchedule, DayOverride
)
from .serializers import (
    EventSerializer, EventInstanceSerializer, SlotSerializer,
    SchedulePatternSerializer, MonthScheduleSerializer, DayOverrideSerializer
)
from .utils.schedule_helper import generate_day_types, return_groups_by_pattern
from .weekdays import Weekday

from schedule.models import PatternMode
from .utils.schedule_helper import group_days_by_cycles
from common.datetime import ensure_timezone


logger = logging.getLogger(__name__)


class UserScopedQuerySetMixin:
    """Фильтрует queryset по текущему пользователю через поле user_lookup."""
    user_lookup = "user"  # имя поля, по которому связана модель с пользователем

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(**{self.user_lookup: self.request.user})


class EventViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = EventSerializer
    queryset = Event.objects.all()  # базовый queryset для миксина

    def perform_create(self, serializer):
        # user выставляем на сервере, а в сериализаторе делаем read_only=True
        serializer.save(user=self.request.user)


class EventInstanceViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = EventInstanceSerializer
    queryset = EventInstance.objects.select_related("parent_event").all()
    # EventInstance -> parent_event -> user
    user_lookup = "parent_event__user"

    def perform_create(self, serializer):
        """Запрещаем создавать инстанс на событие, которое не принадлежит пользователю."""
        parent_event = serializer.validated_data.get("parent_event")
        if parent_event.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You cannot use events that are not yours.")
        serializer.save()

    def perform_update(self, serializer):
        """Тоже защищаем обновление от смены parent_event на чужой."""
        parent_event = serializer.validated_data.get("parent_event")
        if parent_event is not None and parent_event.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You cannot assign someone else's event.")
        serializer.save()


# -----------------------------
# Расширенная выдача вхождений
# -----------------------------
class EventExpandedListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EventSerializer
    queryset = Event.objects.none()

    def get(self, request, *args, **kwargs):
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        if not year or not month:
            raise ValidationError({"detail": "Both 'year' and 'month' query parameters are required."})

        try:
            year = int(year)
            month = int(month)
        except ValueError:
            raise ValidationError({"detail": "'year' and 'month' must be integers."})

        tz = timezone.get_current_timezone()
        debug_mode = settings.DEBUG or (request.query_params.get('debug') == '1')
        errors = []
        debug_notes = []

        # --- helpers ---
        def _first_of_month(dt):
            if dt is None:
                return None
            # приводим к локальному tz и делаем ровно 00:00 первого числа
            if dt.tzinfo is None:
                aware = make_aware(dt, tz)
            else:
                aware = timezone.localtime(dt, tz)
            aware = aware.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return aware

        def _add_months(dt, months):
            # dt — AWARE; крутим месяцы и сохраняем tz корректно
            y = dt.year + (dt.month - 1 + months) // 12
            m = (dt.month - 1 + months) % 12 + 1
            return dt.replace(year=y, month=m)

        def _serialize_datetime(value):
            aware_value = ensure_timezone(value, tz=tz)
            return aware_value.isoformat()

        # --- границы выбранного месяца [start_dt, end_dt] (aware) ---
        start_dt = make_aware(datetime(year, month, 1, 0, 0, 0), tz)
        if month == 12:
            next_month = make_aware(datetime(year + 1, 1, 1, 0, 0, 0), tz)
        else:
            next_month = make_aware(datetime(year, month + 1, 1, 0, 0, 0), tz)
        end_dt = next_month - timedelta(seconds=1)

        events_data = []

        # ⚠️ фильтруем только события текущего пользователя
        events = Event.objects.filter(
            user=request.user
        ).filter(
            Q(start_datetime__lte=end_dt) &
            (Q(end_datetime__gte=start_dt) | Q(end_datetime__isnull=True))
        )[:1000]  # safety cap

        for event in events:
            try:
                rtype = get_recurrence_type(event)

                # =========================
                # A) MONTH-режим (NUMBER_OF_MONTH)
                # =========================
                if event.date_mode == EventDateMode.NUMBER_OF_MONTH:
                    # 1) одиночное "за месяц"
                    if not event.is_recurring_monthly:
                        anchor = _first_of_month(event.start_datetime)
                        if anchor and (start_dt <= anchor <= end_dt):
                            occurrence_id = str(event.id)
                            events_data.append({
                                "id": occurrence_id,
                                "occurrence_id": occurrence_id,
                                "source_event_id": event.id,
                                "instance_id": None,
                                "datetime": _serialize_datetime(anchor),
                                "event": EventSerializer(
                                    event, context={"request": request}
                                ).data,
                                "overlay": None,
                                "is_recurring": False,
                                "recurrence_type": "single",
                            })
                        continue  # MONTH-ветка обработана

                    # 2) повторяемое "каждые N месяцев"
                    interval = int(event.month_interval or 1)
                    series_start = _first_of_month(event.start_datetime)
                    series_end = _first_of_month(event.end_datetime)

                    if not series_start or not series_end:
                        # на валидатор надеемся, но защитимся от битых данных
                        debug_notes.append({
                            "event_id": event.id,
                            "note": "monthly series skipped due to missing series_start/series_end"
                        })
                        continue

                    current = series_start
                    while current <= series_end:
                        if start_dt <= current <= end_dt:
                            current_aware = ensure_timezone(current, tz=tz)
                            instance = EventInstance.objects.filter(
                                parent_event=event,
                                instance_datetime=current_aware
                            ).first()
                            unique_id = f"{event.id}_{int(current_aware.timestamp())}"

                            events_data.append({
                                "id": unique_id,
                                "occurrence_id": unique_id,
                                "source_event_id": event.id,
                                "instance_id": instance.id if instance else None,
                                "datetime": current_aware.isoformat(),
                                "event": EventSerializer(
                                    instance.parent_event if instance else event,
                                    context={"request": request}
                                ).data,
                                "overlay": EventInstanceSerializer(
                                    instance, context={"request": request}
                                ).data if instance else None,
                                "is_recurring": True,
                                "recurrence_type": "monthly",
                            })
                        current = _add_months(current, interval)

                    continue  # MONTH-ветка обработана

                # =========================
                # B) EXACT_DATE (без RRULE) => одиночное
                # =========================
                if rtype == 'single' and not event.recurrence:
                    if start_dt <= event.start_datetime <= end_dt:
                        event_start = ensure_timezone(event.start_datetime, tz=tz)
                        occurrence_id = str(event.id)
                        events_data.append({
                            "id": occurrence_id,
                            "occurrence_id": occurrence_id,
                            "source_event_id": event.id,
                            "instance_id": None,
                            "datetime": event_start.isoformat(),
                            "event": EventSerializer(
                                event, context={"request": request}
                            ).data,
                            "overlay": None,
                            "is_recurring": False,
                            "recurrence_type": "single",
                        })
                    continue

                # =========================
                # C) EXACT_DATE + RRULE
                # =========================
                if event.recurrence:
                    # django-recurrence обычно дружит с naive датами
                    start_naive = make_naive(start_dt, tz)
                    end_naive = make_naive(end_dt, tz)
                    dtstart_naive = datetime(2010, 1, 1, 0, 0, 0)

                    recurrences = event.recurrence.between(
                        start_naive,
                        end_naive,
                        inc=True,
                        dtstart=dtstart_naive
                    )
                    for recurrence in recurrences:
                        # recurrence приходит naive — делаем его aware
                        recurrence_aware = make_aware(recurrence, tz)

                        unique_id = f"{event.id}_{int(recurrence_aware.timestamp())}"
                        normalized = ensure_timezone(recurrence_aware, tz=tz)
                        instance = EventInstance.objects.filter(
                            parent_event=event,
                            instance_datetime=normalized
                        ).first()

                        events_data.append({
                            "id": unique_id,
                            "occurrence_id": unique_id,
                            "source_event_id": event.id,
                            "instance_id": instance.id if instance else None,
                            "datetime": normalized.isoformat(),
                            "event": EventSerializer(
                                instance.parent_event if instance else event,
                                context={"request": request}
                            ).data,
                            "overlay": EventInstanceSerializer(
                                instance, context={"request": request}
                            ).data if instance else None,
                            "is_recurring": True,
                            "recurrence_type": "rrule",
                        })

            except Exception as e:
                # Лог в консоль со стеком и контекстом
                logger.exception(
                    "all_events crash on event %s (user=%s, year=%s, month=%s)",
                    getattr(event, "id", None), getattr(request.user, "id", None), year, month
                )
                # В ответ для дебага (если можно)
                errors.append({
                    "event_id": getattr(event, "id", None),
                    "msg": str(e),
                    "rtype": locals().get("rtype", None),
                    "date_mode": getattr(event, "date_mode", None),
                })
                continue

        # Ответ
        payload = events_data
        if debug_mode:
            payload = {
                "events": events_data,
                "errors": errors,
                "meta": {
                    "user_id": getattr(request.user, "id", None),
                    "year": year,
                    "month": month,
                    "count_events": len(events_data),
                    "count_errors": len(errors),
                    "notes": debug_notes,
                }
            }
        return Response(payload)


def group_days_by_iso_week(days):
    """
    Принимает days: List[dict] с ключом 'date' (YYYY-MM-DD) и возвращает List[List[dict]],
    где каждая вложенная группа — это дни одной ISO-недели.
    """
    if not days:
        return []

    def _week_key(dstr: str):
        # Безопасно парсим YYYY-MM-DD
        dt = date.fromisoformat(dstr)
        # ISO-неделя зависит от года/недели (на стыках года важна пара (year, week))
        iso_year, iso_week, _ = dt.isocalendar()
        return (iso_year, iso_week)

    groups = []
    current_group = []
    current_key = None

    for day in days:
        d = day.get("date")
        if not isinstance(d, str):
            # пропустим странные элементы
            continue

        wk = _week_key(d)
        if current_key is None:
            current_key = wk
            current_group = [day]
        elif wk == current_key:
            current_group.append(day)
        else:
            groups.append(current_group)
            current_key = wk
            current_group = [day]

    if current_group:
        groups.append(current_group)

    return groups


class DeleteEventOrOccurrenceView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        event_id = kwargs.get('event_id')
        instance_ts = request.query_params.get('instance_datetime')

        if not instance_ts:
            # Удаляем корневое событие
            event = get_object_or_404(Event, pk=event_id)
            event.delete()
            return Response({"detail": "Event deleted."}, status=status.HTTP_204_NO_CONTENT)

        # Обрабатываем удаление отдельного вхождения
        try:
            instance_dt = datetime.fromisoformat(instance_ts)
        except ValueError:
            return Response({"detail": "Invalid datetime format. Use ISO format with timezone."}, status=status.HTTP_400_BAD_REQUEST)

        if timezone.is_naive(instance_dt):
            return Response({"detail": "Datetime must include timezone information (e.g. '+03:00')."}, status=status.HTTP_400_BAD_REQUEST)

        instance_dt = ensure_timezone(instance_dt, tz=timezone.get_current_timezone())

        event = get_object_or_404(Event, pk=event_id)

        instance, created = EventInstance.objects.get_or_create(
            parent_event=event,
            instance_datetime=instance_dt,
            defaults={"status": CompletionStatus.CANCELLED}
        )

        if not created:
            instance.status = CompletionStatus.CANCELLED
            instance.save()

        return Response({"detail": "Occurrence cancelled."}, status=status.HTTP_200_OK)


class UpdateOccurrenceStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        event_id = kwargs.get('event_id')
        instance_ts = request.data.get('instance_datetime')
        new_status = request.data.get('status')
        is_completed = request.data.get('is_completed')

        if not instance_ts or not new_status:
            return Response({"detail": "Both instance_datetime and status are required."}, status=400)

        try:
            instance_dt = datetime.fromisoformat(instance_ts)
        except ValueError:
            return Response({"detail": "Invalid datetime format. Use ISO format with timezone."}, status=400)

        if timezone.is_naive(instance_dt):
            return Response({"detail": "Datetime must include timezone information (e.g. '+03:00')."}, status=400)

        instance_dt = ensure_timezone(instance_dt, tz=timezone.get_current_timezone())

        if new_status not in CompletionStatus.values:
            return Response({"detail": "Invalid status."}, status=400)

        event = get_object_or_404(Event, pk=event_id)

        instance, _ = EventInstance.objects.get_or_create(
            parent_event=event,
            instance_datetime=instance_dt
        )
        instance.status = new_status
        instance.is_completed = is_completed
        instance.save()

        return Response({"detail": "Status updated."})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def schedule_preview(request):
    """
    Возвращает предварительный просмотр расписания за указанный год и месяц.
    В ответе:
      - список дней с типами (work/off/...),
      - pattern для фронта,
    """
    user_id = request.query_params.get('user')

    # --- Проверка и парсинг параметров ---
    try:
        year = int(request.query_params.get('year'))
        month = int(request.query_params.get('month'))
        user_id = int(user_id) if user_id is not None else None
    except (ValueError, TypeError):
        return Response({'error': 'Неверные параметры year/month/user'}, status=400)

    if user_id is None:
        return Response({'error': 'Параметр user обязателен'}, status=400)

    # --- Получаем расписание ---
    User = get_user_model()
    user_obj = User.objects.get(pk=user_id)

    schedule, created = MonthSchedule.get_or_create_for_month(user_obj, year, month)
    # 🛡️ на случай, если у MonthSchedule ещё не выбран pattern
    pattern_data = SchedulePatternSerializer(schedule.pattern).data if schedule.pattern else None

    # --- Генерация дней ---
    start_date = date(year, month, 1)
    _, days_in_month = calendar.monthrange(year, month)
    try:
        day_types = generate_day_types(schedule)
    except ValueError as e:
        return Response({'error': str(e)}, status=400)

    # --- Генерация дней ---
    days = []
    for i, day_type in enumerate(day_types):
        d = start_date + timedelta(days=i)
        days.append({
            "date": d.isoformat(),  # 'YYYY-MM-DD'
            "day": d.day,
            "weekday": Weekday.get_day_by_number(d.isoweekday(), format_type="short_RU"),
            "day_type": day_type,
            "is_today": d == date.today(),
            "group_id": None,
            "overrides": [],
            "notes": "",
        })

    # ✅ Нормализуем ключи под фронт: day_type -> type
    normalized_days = []
    for item in days:
        new_item = dict(item)
        new_item["type"] = new_item.pop("day_type")
        normalized_days.append(new_item)
    days = normalized_days

    # --- Группы по ISO-неделям из уже нормализованных days
    if schedule.pattern and schedule.pattern.mode == PatternMode.WEEKDAY:
        groups = group_days_by_iso_week(days)  # недельная нарезка (пн–вс)
    else:
        groups = group_days_by_cycles(days, schedule.pattern)

    payload = {
        "year": year,
        "month": month,
        "pattern": pattern_data,
        "grouping_mode": "week" if schedule.pattern and schedule.pattern.mode == PatternMode.WEEKDAY else "type_runs",
        "groups": groups,
        "days": days,
    }
    return Response(payload)


def get_recurrence_type(event) -> str:
    if event.date_mode == EventDateMode.NUMBER_OF_MONTH:
        if event.is_recurring_monthly:
            return 'monthly'
        else:
            return 'single'
    if event.recurrence:
        return 'rrule'
    return 'single'


class SlotViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Slot.objects.all()
    serializer_class = SlotSerializer


class SchedulePatternViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = SchedulePattern.objects.all()
    serializer_class = SchedulePatternSerializer


class MonthScheduleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = MonthSchedule.objects.all()
    serializer_class = MonthScheduleSerializer


class DayOverrideViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = DayOverride.objects.all()
    serializer_class = DayOverrideSerializer
