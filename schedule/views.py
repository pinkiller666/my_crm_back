from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from rest_framework.exceptions import ValidationError
from datetime import datetime, timedelta
from django.db.models import Q

from common.choices import EventDateMode
from .weekdays import Weekday
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, generics, status
from .models import CompletionStatus
import calendar
from datetime import date
from django.contrib.auth import get_user_model

from .utils.schedule_helper import generate_day_types, return_groups_by_pattern

from .models import (
    Event, EventInstance, Slot,
    SchedulePattern, MonthSchedule, DayOverride
)
from .serializers import (
    EventSerializer, EventInstanceSerializer, SlotSerializer,
    SchedulePatternSerializer, MonthScheduleSerializer, DayOverrideSerializer
)


class UserScopedQuerySetMixin:
    user_lookup = "user"  # имя поля, по которому связана модель с пользователем

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(**{self.user_lookup: self.request.user})


class EventViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = EventSerializer

    # ВАЖНО: нужен базовый queryset, чтобы super().get_queryset() в миксине не упал
    queryset = Event.objects.all()

    def perform_create(self, serializer):
        # user выставляем на сервере, а в сериализаторе делаем read_only=True
        serializer.save(user=self.request.user)


class EventInstanceViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = EventInstanceSerializer

    # Даем базовый queryset, чтобы super().get_queryset() не упал
    queryset = EventInstance.objects.select_related("event").all()

    # ⛳️ Переопределяем путь до владельца:
    # EventInstance -> event -> user
    user_lookup = "event__user"

    def perform_create(self, serializer):
        """Запрещаем создавать инстанс на событие, которое не принадлежит пользователю."""
        event = serializer.validated_data.get("event")
        if event.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You cannot use events that are not yours.")
        serializer.save()

    def perform_update(self, serializer):
        """Тоже защищаем обновление от смены event на чужой."""
        event = serializer.validated_data.get("event")
        if event is not None and event.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You cannot assign someone else's event.")
        serializer.save()


# БЭК | views.py | EventExpandedListView — ЗАМЕНИТЬ КЛАСС ЦЕЛИКОМ
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

        # --- helpers (локально, чтобы не менять импорты модуля) ---
        def _first_of_month(dt):
            if dt is None:
                return None
            # нормализуем к 1-му числу и 00:00, сохраняя tz
            return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=tz)

        def _add_months(dt, months):
            # безопасно двигаемся на N месяцев вперёд; day=1 => всегда валидно
            y = dt.year + (dt.month - 1 + months) // 12
            m = (dt.month - 1 + months) % 12 + 1
            return dt.replace(year=y, month=m, tzinfo=tz)

        # --- границы выбранного месяца [start_dt, end_dt] ---
        start_dt = datetime(year, month, 1, 0, 0, 0).replace(tzinfo=tz)
        if month == 12:
            next_month = datetime(year + 1, 1, 1, 0, 0, 0).replace(tzinfo=tz)
        else:
            next_month = datetime(year, month + 1, 1, 0, 0, 0).replace(tzinfo=tz)
        end_dt = next_month - timedelta(seconds=1)

        events_data = []

        # ⚠️ фильтруем только события текущего пользователя
        events = Event.objects.filter(
            user=request.user
        ).filter(
            Q(start_datetime__lte=end_dt) &
            (Q(end_datetime__gte=start_dt) | Q(end_datetime__isnull=True))
        )
        events = events[:1000]
        for event in events:
            rtype = get_recurrence_type(event)

            # =========================
            # A) MONTH-режим (NUMBER_OF_MONTH)
            # =========================
            if event.date_mode == EventDateMode.NUMBER_OF_MONTH:
                # 1) одиночное "за месяц"
                if not event.is_recurring_monthly:
                    anchor = _first_of_month(event.start_datetime)
                    if anchor and (start_dt <= anchor <= end_dt):
                        occurrence_id = str(event.id)  # унификация: всегда строка
                        events_data.append({
                            # совместимость: старое поле "id" остаётся
                            "id": occurrence_id,
                            "occurrence_id": occurrence_id,
                            "source_event_id": event.id,
                            "instance_id": None,
                            "datetime": anchor,
                            "event": EventSerializer(event).data,
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
                    continue

                current = series_start
                while current <= series_end:
                    if start_dt <= current <= end_dt:
                        instance = EventInstance.objects.filter(
                            parent_event=event,
                            instance_datetime=current
                        ).first()
                        unique_id = f"{event.id}_{int(current.timestamp())}"

                        events_data.append({
                            "id": unique_id,  # совместимость
                            "occurrence_id": unique_id,
                            "source_event_id": event.id,
                            "instance_id": instance.id if instance else None,
                            "datetime": current,
                            "event": EventSerializer(instance.parent_event if instance else event).data,
                            "overlay": EventInstanceSerializer(instance).data if instance else None,
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
                    occurrence_id = str(event.id)
                    events_data.append({
                        "id": occurrence_id,
                        "occurrence_id": occurrence_id,
                        "source_event_id": event.id,
                        "instance_id": None,
                        "datetime": event.start_datetime,
                        "event": EventSerializer(event).data,
                        "overlay": None,
                        "is_recurring": False,
                        "recurrence_type": "single",
                    })
                continue

            # =========================
            # C) EXACT_DATE + RRULE
            # =========================
            if event.recurrence:
                recurrences = event.recurrence.between(
                    start_dt,
                    end_dt,
                    inc=True,
                    dtstart=datetime(2010, 1, 1, 0, 0).replace(tzinfo=tz)
                )
                for recurrence in recurrences:
                    unique_id = f"{event.id}_{int(recurrence.timestamp())}"
                    instance = EventInstance.objects.filter(
                        parent_event=event,
                        instance_datetime=recurrence
                    ).first()

                    events_data.append({
                        "id": unique_id,  # совместимость
                        "occurrence_id": unique_id,
                        "source_event_id": event.id,
                        "instance_id": instance.id if instance else None,
                        "datetime": recurrence,
                        "event": EventSerializer(instance.parent_event if instance else event).data,
                        "overlay": EventInstanceSerializer(instance).data if instance else None,
                        "is_recurring": True,
                        "recurrence_type": "rrule",
                    })

        return Response(events_data)


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
            return Response({"detail": "Invalid datetime format. Use ISO format."}, status=status.HTTP_400_BAD_REQUEST)

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
            return Response({"detail": "Invalid datetime format."}, status=400)

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
      - группы (длины недельных или рабочих блоков).
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

    pattern_data = SchedulePatternSerializer(schedule.pattern).data

    # --- Генерация дней ---
    start_date = date(year, month, 1)
    _, days_in_month = calendar.monthrange(year, month)
    try:
        day_types = generate_day_types(schedule)
    except ValueError as e:
        return Response({'error': str(e)}, status=400)

    days = []
    for i, day_type in enumerate(day_types):
        d = start_date + timedelta(days=i)
        days.append({
            'date': d.isoformat(),
            'day': d.day,
            'weekday': Weekday.get_day_by_number(d.isoweekday(), format_type='short_RU'),
            'type': day_type,
        })

    # --- Группы ---
    lengths, labels = return_groups_by_pattern(schedule)
    groups = {'lengths': lengths, 'labels': labels}

    # --- Финальный ответ ---
    return Response({
        "year": year,
        "month": month,
        "days": days_payload  # собран строго с ключами: date, weekday, day_type, is_today, group_id, overrides, notes
    })


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
