from recurrence.fields import RecurrenceField
from django.utils import timezone

from copy import deepcopy
from datetime import datetime, timedelta
import calendar

from decimal import Decimal, ROUND_FLOOR
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from datetime import date
from django.db.models import Q
from common.choices import EventDateMode
from common.datetime import ensure_timezone


class CompletionStatus(models.TextChoices):
    INCOMPLETE = 'incomplete', 'INCOMPLETE'
    COMPLETE = 'complete', 'COMPLETE'
    CANCELLED = 'cancelled', 'CANCELLED'
    ON_PAUSE = 'on_pause', 'ON_PAUSE'
    IN_PROCESS = 'in_process', 'IN_PROCESS'


class DayType(models.TextChoices):
    WORK = 'work', 'Рабочий'
    OFF = 'off', 'Выходной'
    HOLIDAY = 'holiday', 'Праздник'
    VACATION = 'vacation', 'Отпуск'
    TASK = 'task', 'Дело'


class Event(models.Model):
    class EventType(models.TextChoices):
        EVENT = 'event', 'Событие'
        TASK = 'task', 'Задача'

    class CategoryChoices(models.TextChoices):
        WORK = 'work', 'Рабочее'
        LIFE = 'life', 'Пожизневые'
        SPORT = 'sport', 'Спорт'
        MEDICAL = 'medical', 'Медицина'

    class TypeChoices(models.TextChoices):
        FUN = 'fun', 'Кайфовые'
        ROUTINE = 'routine', 'Рутина'
        IMPORTANT = 'important', 'Важные'
        HEAVY = 'heavy', 'Трудоемкие'
        GROSS = 'gross', 'Мерзкие'

    is_recurring_monthly = models.BooleanField(
        default=False,
        help_text="True — повторяемое по месяцам (интервал в месяцах, старт/финиш берём из "
                  "start_datetime/end_datetime)."
    )
    month_interval = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Интервал в месяцах (1..12) для повторяемого MONTH-режима."
    )

    event_type = models.CharField(max_length=10, choices=EventType.choices, default=EventType.EVENT)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    account = models.ForeignKey("accounting.Account", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='events')
    date_mode = models.CharField(
        max_length=20,
        choices=EventDateMode.choices,
        default=EventDateMode.EXACT_DATE
    )
    recurrence = RecurrenceField(blank=True, null=True, include_dtstart=False)
    start_datetime = models.DateTimeField(default=timezone.now)
    end_datetime = models.DateTimeField(blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=50, choices=CompletionStatus.choices, default=CompletionStatus.INCOMPLETE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='events',
        null=False, blank=False
    )

    month_year = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Год для режима NUMBER_OF_MONTH (например, 2025)."
    )
    month_number = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Месяц (1-12) для режима NUMBER_OF_MONTH."
    )

    # # --- Поля для NUMBER_OF_WEEK ---
    # # nth: 1..5 или -1 (=последняя такая неделя в месяце)
    # nth_in_month = models.SmallIntegerField(
    #     null=True, blank=True,
    #     help_text="Номер недели в месяце (1..5 или -1 для последней). Используется в NUMBER_OF_WEEK."
    # )
    # # weekday: 0=Mon .. 6=Sun (как в datetime.weekday())
    # weekday_in_month = models.SmallIntegerField(
    #     null=True, blank=True,
    #     help_text="День недели (0=Пн .. 6=Вс). Используется в NUMBER_OF_WEEK."
    # )

    is_balance_correction = models.BooleanField(default=False)

    # Доп. поля, если это задача
    date_day = models.DateField(null=True, blank=True)
    category = models.CharField(max_length=32, choices=CategoryChoices.choices, blank=True, null=True)
    type = models.CharField(max_length=32, choices=TypeChoices.choices, blank=True, null=True)

    # БЭК | models.py | Event.clean (расширение)
    def clean(self):
        super().clean()

        # Требование к задачам из твоего кода
        if self.event_type == self.EventType.TASK and self.date_day is None:
            raise ValidationError("Поле 'date_day' обязательно для задач.")

        # --- Валидация по режимам даты ---
        mode = self.date_mode

        if mode == EventDateMode.EXACT_DATE:
            # Разрешаем: одиночная дата И/ИЛИ recurrence
            if not self.start_datetime and not self.recurrence:
                raise ValidationError(
                    "Для режима 'Точная дата' нужно указать start_datetime или recurrence."
                )

        elif mode == EventDateMode.NUMBER_OF_MONTH:
            # В MONTH-режиме нельзя использовать RecurrenceField
            if self.recurrence:
                raise ValidationError("В режиме 'Номер месяца' поле 'recurrence' использовать нельзя.")

            if self.is_recurring_monthly:
                # Повторяемое «по месяцам»
                if not self.month_interval:
                    raise ValidationError("Для повторяемого MONTH-события укажите 'month_interval' (1..12).")
                try:
                    iv = int(self.month_interval)
                    if iv < 1 or iv > 12:
                        raise ValidationError("Поле 'month_interval' должно быть в диапазоне 1..12.")
                except (TypeError, ValueError):
                    raise ValidationError("Поле 'month_interval' должно быть целым числом 1..12.")
                if not self.start_datetime or not self.end_datetime:
                    raise ValidationError(
                        "Для повторяемого MONTH-события укажите 'start_datetime' (старт, включительно) "
                        "и 'end_datetime' (финиш, включительно)."
                    )
                # Сравним пары (год, месяц): start <= end
                start_pair = (self.start_datetime.year, self.start_datetime.month)
                end_pair = (self.end_datetime.year, self.end_datetime.month)
                if start_pair > end_pair:
                    raise ValidationError(
                        "В MONTH-режиме дата начала должна быть не позже даты окончания (по год/месяц).")
            else:
                # Неповторяемое «за месяц»: используем только start_datetime (год/месяц), end_datetime не обязателен
                if not self.start_datetime:
                    raise ValidationError("Для неповторяемого MONTH-события укажите 'start_datetime' (год+месяц).")
                # Интервал при одиночном MONTH-событии не должен быть задан
                if self.month_interval:
                    raise ValidationError("Поле 'month_interval' заполняется только для повторяемого MONTH-события.")

    def save(self, *args, **kwargs):
        # синхронизация статуса/галочки
        if self.status == CompletionStatus.COMPLETE:
            self.is_completed = True
        else:
            self.is_completed = False

        # 👇 автоподстановка счёта, если не указан
        if self.account is None and self.user_id:
            from accounting.models import Account  # локальный импорт, чтобы избежать циклов
            primary = Account.objects.filter(user_id=self.user_id, is_primary=True).first()
            if primary is None:
                # если по каким-то причинам первичного нет — создадим его
                primary = Account.objects.create(
                    user_id=self.user_id,
                    name="Основной счёт",
                    is_primary=True,
                    balance=0
                )
            self.account = primary
        current_tz = timezone.get_current_timezone()
        self.start_datetime = ensure_timezone(self.start_datetime, tz=current_tz)
        self.end_datetime = ensure_timezone(self.end_datetime, tz=current_tz)
        if self.date_mode == EventDateMode.NUMBER_OF_MONTH:
            if self.start_datetime:
                self.start_datetime = self.start_datetime.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if self.is_recurring_monthly and self.end_datetime:
                self.end_datetime = self.end_datetime.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Событие или задача"
        verbose_name_plural = "События и задачи"

    def __str__(self):
        return f"[{self.get_event_type_display()}] {self.name or self.title or 'Без названия'}"


    def get_occurrences(self, start_dt, end_dt, tz):
        """
        Возвращает список occurrence-событий в диапазоне [start_dt, end_dt].
        """
        occurrences = []
        mode = self.date_mode

        def _copy_with_datetime(dt: datetime):
            from copy import deepcopy
            copy_obj = deepcopy(self)
            copy_obj.id = None
            copy_obj.is_occurrence = True
            copy_obj.start_datetime = dt
            if self.duration_minutes:
                copy_obj.end_datetime = dt + timedelta(minutes=self.duration_minutes)
            return copy_obj

        # 1) NUMBER_OF_MONTH
        if mode == EventDateMode.NUMBER_OF_MONTH:
            # a) без recurrence -> одно вхождение на 1-е число указанного месяца
            if not self.recurrence:
                if self.month_year and self.month_number:
                    dt = datetime(int(self.month_year), int(self.month_number), 1, 0, 0, tzinfo=tz)
                    if start_dt <= dt <= end_dt:
                        occurrences.append(_copy_with_datetime(dt))
                return occurrences

            # b) с recurrence (ожидаем RRULE:FREQ=MONTHLY ...):
            #    используем between(), якоримся на dtstart (первое число указанного месяца)
            if self.month_year and self.month_number:
                dtstart = datetime(int(self.month_year), int(self.month_number), 1, 0, 0, tzinfo=tz)
            else:
                # если не указали месяц/год — fallback к 2010-01-01
                dtstart = datetime(2010, 1, 1, 0, 0, tzinfo=tz)

            recurrences = self.recurrence.between(
                start_dt, end_dt, inc=True, dtstart=dtstart
            )
            for dt in recurrences:
                # применяем кастомные инстансы, если есть
                instance = self.instances.filter(instance_datetime=dt).first()
                copy_obj = _copy_with_datetime(dt)
                if instance:
                    copy_obj.status = instance.status
                    copy_obj.is_completed = instance.is_completed
                occurrences.append(copy_obj)
            return occurrences

        # 2) EXACT_DATE без recurrence -> одиночная дата
        if mode == EventDateMode.EXACT_DATE and self.start_datetime and not self.recurrence:
            if start_dt <= self.start_datetime <= end_dt:
                occurrences.append(_copy_with_datetime(self.start_datetime))
            return occurrences

        # 3) EXACT_DATE с recurrence
        if self.recurrence:
            recurrences = self.recurrence.between(
                start_dt, end_dt, inc=True,
                dtstart=datetime(2010, 1, 1, 0, 0).replace(tzinfo=tz)
            )
            for dt in recurrences:
                instance = self.instances.filter(instance_datetime=dt).first()
                copy_obj = _copy_with_datetime(dt)
                if instance:
                    copy_obj.status = instance.status
                    copy_obj.is_completed = instance.is_completed
                occurrences.append(copy_obj)

        return occurrences


class EventInstance(models.Model):
    parent_event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='instances')
    instance_datetime = models.DateTimeField()
    status = models.CharField(max_length=50, choices=CompletionStatus.choices, default=CompletionStatus.INCOMPLETE)
    is_completed = models.BooleanField(default=False)
    modified_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # синхронизируем is_completed со статусом
        if self.status == CompletionStatus.COMPLETE:
            self.is_completed = True
        else:
            self.is_completed = False
        self.instance_datetime = ensure_timezone(self.instance_datetime, tz=timezone.get_current_timezone())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.parent_event.name} ({self.instance_datetime.strftime('%Y-%m-%d %H:%M')})"


class Slot(models.Model):
    date_range = models.DateTimeField()
    status = models.CharField(max_length=255, choices=[('available', 'Available'), ('booked', 'Booked')])

    def __str__(self):
        return f"Slot {self.date_range} - {self.status}"


class PatternMode(models.TextChoices):
    ALTERNATING = 'alternating', 'Чередование блоков'
    WEEKDAY = 'weekday', 'По дням недели'


def validate_quarter_hours(value: Decimal):
    # кратно 0.25 (15 минут)
    mult = (value * Decimal('4'))
    if mult != mult.to_integral_value(rounding=ROUND_FLOOR):
        raise ValidationError('Длительность должна быть кратна 0.25 часа (15 минут).')


def default_weekday_map():
    return {"mon": "work", "tue": "work", "wed": "work", "thu": "work", "fri": "work", "sat": "off", "sun": "off"}


class SchedulePattern(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    # РЕЖИМ ШАБЛОНА
    mode = models.CharField(
        max_length=20,
        choices=PatternMode.choices,
        default=PatternMode.ALTERNATING
    )

    # ALTERNATING
    days_off_at_start = models.PositiveSmallIntegerField(default=0)
    pattern_after_start = models.JSONField(default=list)

    # WEEKDAY: JSON вида {"mon":"work","tue":"work","wed":"off","thu":"work","fri":"work","sat":"off","sun":"off"}
    weekday_map = models.JSONField(null=True, blank=True, default=None)

    last_day_always_working = models.BooleanField(default=False)

    # Часы, кратно 0.25
    working_day_duration = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('4.00'),
        validators=[validate_quarter_hours]
    )

    class Meta:
        verbose_name_plural = 'Шаблоны расписания'

    @property
    def cycle_length(self) -> int:
        """Сумма элементов pattern_after_start (без падений на мусоре)."""
        if self.mode != PatternMode.ALTERNATING:
            return 0
        seq = self.pattern_after_start or []
        total = 0
        for item in seq:
            try:
                total += int(item)
            except (TypeError, ValueError):
                continue
        return total

    def clean(self):
        errors = {}

        # mutually exclusive modes
        if self.mode == PatternMode.ALTERNATING:
            # weekday_map не должен быть заполнен
            if self.weekday_map:
                errors['weekday_map'] = 'В режиме ALTERNATING weekday_map должен быть пустым.'
            # pattern_after_start: чётная длина, все >0
            seq = self.pattern_after_start or []
            if len(seq) == 0:
                errors['pattern_after_start'] = 'Должен быть хотя бы один элемент (например, [2,2]).'
            elif len(seq) % 2 != 0:
                errors['pattern_after_start'] = 'Количество элементов должно быть чётным (например, 2,2 или 2,1,2,2).'
            else:
                for i, item in enumerate(seq):
                    try:
                        iv = int(item)
                        if iv <= 0:
                            raise ValueError
                    except Exception:
                        errors[
                            'pattern_after_start'] = f'Все элементы должны быть положительными целыми. Ошибка на позиции {i + 1}.'
                        break

            # days_off_at_start уже не может быть < 0 по типу поля

        elif self.mode == PatternMode.WEEKDAY:
            # pattern_after_start должен быть пустым, days_off_at_start = 0
            if self.pattern_after_start:
                errors['pattern_after_start'] = 'В режиме WEEKDAY pattern_after_start должен быть пустым.'
            if self.days_off_at_start != 0:
                errors['days_off_at_start'] = 'В режиме WEEKDAY days_off_at_start должен быть равен 0.'
            # validate weekday_map
            required_keys = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            if not isinstance(self.weekday_map, dict):
                errors['weekday_map'] = 'Должен быть словарь с ключами mon..sun.'
            else:
                missing = [k for k in required_keys if k not in self.weekday_map]
                if missing:
                    errors['weekday_map'] = f'Отсутствуют ключи: {", ".join(missing)}.'
                else:
                    valid_values = {DayType.WORK, DayType.OFF}
                    for k in required_keys:
                        v = self.weekday_map.get(k)
                        if v not in valid_values:
                            errors['weekday_map'] = 'Значения должны быть "work" или "off".'
                            break

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name


def current_year():
    return date.today().year


def current_month():
    return date.today().month


class MonthSchedule(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    year = models.PositiveIntegerField(default=current_year)
    month = models.PositiveSmallIntegerField(default=current_month)
    pattern = models.ForeignKey(SchedulePattern, on_delete=models.PROTECT, related_name='month_schedules')

    class Meta:
        unique_together = ('user', 'year', 'month')
        verbose_name_plural = 'Расписания на месяц'
        constraints = [
            models.CheckConstraint(
                check=Q(month__gte=1) & Q(month__lte=12),
                name='month_between_1_and_12',
            ),
        ]

    def __str__(self):
        # get_username() безопаснее, чем username
        u = getattr(self.user, 'get_username', None)
        uname = u() if callable(u) else getattr(self.user, 'username', str(self.user_id))
        return f"{uname} — {self.year}-{self.month:02d}: {self.pattern.name}"

    @classmethod
    def get_or_create_for_month(cls, user, year, month):
        """
        Возвращает (MonthSchedule, created)
        - если на указанный месяц уже есть расписание → возвращает его;
        - если нет → берёт самое свежее предыдущее;
        - если вообще ничего нет → создаёт на основе шаблона 'Классика'.
        """
        # 1️⃣ Проверяем, есть ли уже расписание на этот месяц
        schedule = cls.objects.filter(user=user, year=year, month=month).first()
        if schedule:
            return schedule, False

        # 2️⃣ Если нет — ищем ближайшее прошлое
        current_serial = year * 12 + month
        prev_schedule = (
            cls.objects.filter(user=user)
            .annotate(serial=models.F("year") * 12 + models.F("month"))
            .filter(serial__lt=current_serial)
            .order_by("-year", "-month")
            .first()
        )
        if prev_schedule:
            return cls.objects.create(
                user=user,
                year=year,
                month=month,
                pattern=prev_schedule.pattern
            ), True

        # 3️⃣ Если нет вообще никаких расписаний — берём 'Классику'
        from schedule.models import SchedulePattern
        default_pattern = SchedulePattern.objects.filter(name__iexact="Классика").first()
        if default_pattern is None:
            # fallback на случай, если ready() не успел
            from schedule.models import PatternMode
            default_pattern = SchedulePattern.objects.create(
                name="Классика",
                mode=PatternMode.WEEKDAY,
                days_off_at_start=0,
                pattern_after_start=[],
                weekday_map={
                    "mon": "work",
                    "tue": "work",
                    "wed": "work",
                    "thu": "work",
                    "fri": "work",
                    "sat": "off",
                    "sun": "off",
                },
                description="Пятидневка: Пн–Пт рабочие, Сб–Вс выходные.",
            )

        return cls.objects.create(
            user=user,
            year=year,
            month=month,
            pattern=default_pattern
        ), True


class DayOverride(models.Model):
    month_schedule = models.ForeignKey(MonthSchedule, on_delete=models.CASCADE, related_name="overrides")
    date = models.DateField()
    type = models.CharField(max_length=20, choices=DayType.choices, default=DayType.OFF)
    comment = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Исключения расписания'
        constraints = [
            models.UniqueConstraint(fields=['month_schedule', 'date'], name='unique_day_per_monthschedule')
        ]

    def __str__(self):
        return f"{self.date}: {self.type}"
