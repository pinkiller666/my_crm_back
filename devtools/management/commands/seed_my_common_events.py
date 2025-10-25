# -*- coding: utf-8 -*-
# БЭК: backend/devtools/management/commands/seed_my_common_events.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import time, timedelta, datetime
from decimal import Decimal
from django.contrib.auth import get_user_model

from recurrence import Recurrence, Rule, WEEKLY, TH
from schedule.models import Event, SchedulePattern, PatternMode, MonthSchedule  # 🆕 добавили три модели


def next_weekday(dt, target_weekday: int):
    """
    Вернёт ближайшую дату с днём недели target_weekday (0=Пн ... 6=Вс).
    Если сегодня нужный день — вернёт сегодня.
    """
    days_ahead = (target_weekday - dt.weekday()) % 7
    return dt + timedelta(days=days_ahead)


class Command(BaseCommand):
    help = "Создаёт/обновляет мои стандартные повторяемые события (например, уборщица по четвергам)."

    def handle(self, *args, **options):
        User = get_user_model()

        # 1) Гарантируем пользователя
        user_obj = User.objects.filter(username="nikita").first()
        if user_obj is None:
            user_obj = User.objects.create_user(
                username="nikita",
                email="nikita@example.com",
                password="nikita",
            )

        # 2) Параметры события
        name = "🧹 Уборщица"
        amount = Decimal("-3500.00")
        start_at = time(hour=13, minute=0)
        duration_minutes = 4 * 60  # 4 часа

        # 3) Ближайший четверг 13:00 в текущем TZ
        today = timezone.localdate()
        # четверг = 3 (Пн=0)
        start_date = next_weekday(today, 3)
        start_dt_naive = datetime.combine(start_date, start_at)
        start_dt = timezone.make_aware(start_dt_naive, timezone.get_current_timezone())

        # 4) RRULE: еженедельно по четвергам
        weekly_th_rule = Rule(freq=WEEKLY, byday=[TH])
        recur = Recurrence(rrules=[weekly_th_rule])

        # 5) Создаём/обновляем
        obj, created = Event.objects.update_or_create(
            name=name,
            defaults=dict(
                event_type=Event.EventType.EVENT,
                description="Регулярная уборка по четвергам",
                amount=amount,
                recurrence=recur,            # передаём Recurrence-объект
                start_datetime=start_dt,     # первая опорная дата/время
                end_datetime=None,
                duration_minutes=duration_minutes,
                is_active=True,
                is_completed=False,
                tags=[],                     # ок: новый список при каждом запуске
                category=Event.CategoryChoices.LIFE,
                type=Event.TypeChoices.ROUTINE,
                user=user_obj,               # ⬅️ ВАЖНО: инстанс пользователя
                # account не указываем — если в save() Event подставляет primary-аккаунт юзера
            ),
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"✅ Создано событие: {obj.name}"))
        else:
            self.stdout.write(self.style.WARNING(f"♻️ Обновлено событие: {obj.name}"))

        self._ensure_month_pattern_for_user(user_obj)

    def _ensure_month_pattern_for_user(self, user):
        """
        Назначает пользователю шаблон:
        '4 выходных, потом 2 через 2 — последний день рабочий'
        на текущий и следующий месяц. Идемпотентно.
        """
        # 1) Берём/создаём нужный шаблон (на случай если его ещё нет)
        pat_name = "4 выходных, потом 2 через 2 — последний день рабочий"
        pat_defaults = dict(
            description="Автосозданный базовый шаблон (ALTERNATING).",
            mode=PatternMode.ALTERNATING,
            days_off_at_start=4,
            pattern_after_start=[2, 2],
            weekday_map=None,
            last_day_always_working=True,
            working_day_duration=Decimal("4.00"),
        )
        pattern, created_pat = SchedulePattern.objects.get_or_create(
            name=pat_name, defaults=pat_defaults
        )
        if not created_pat:
            # мягкая синхронизация, если вдруг меняли руками
            changed = False
            for k, v in pat_defaults.items():
                if getattr(pattern, k) != v:
                    setattr(pattern, k, v)
                    changed = True
            if changed:
                pattern.full_clean()
                pattern.save()

        # 2) Текущий и следующий месяцы
        today = timezone.localdate()
        year, month = today.year, today.month
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

        for y, m in ((year, month), (next_year, next_month)):
            ms, created_ms = MonthSchedule.objects.get_or_create(
                user=user, year=y, month=m, defaults={"pattern": pattern}
            )
            if created_ms:
                self.stdout.write(self.style.SUCCESS(
                    f"📅 Создан MonthSchedule: {user} — {y}-{m:02d} → «{pattern.name}»"
                ))
            else:
                if ms.pattern_id != pattern.id:
                    ms.pattern = pattern
                    ms.save(update_fields=["pattern"])
                    self.stdout.write(self.style.WARNING(
                        f"♻️ Обновлён MonthSchedule: {user} — {y}-{m:02d} → «{pattern.name}»"
                    ))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"✓ Уже назначен: {user} — {y}-{m:02d} → «{pattern.name}»"
                    ))
