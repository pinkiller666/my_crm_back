# BACK — admin.py
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import (
    EventInstance, Event, Slot,
    SchedulePattern, MonthSchedule, DayOverride,
    PatternMode, DayType
)


# --- Твои существующие админы оставляем как есть (я ниже трону только SchedulePattern/MonthSchedule) ---

@admin.register(EventInstance)
class EventInstanceAdmin(admin.ModelAdmin):
    list_display = ("parent_event", "instance_datetime", "status", "modified_at")
    list_filter = ("status",)
    ordering = ("-modified_at",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "account", "start_datetime", "status", "is_active")
    search_fields = ("name", "description", "account__name")
    list_filter = ("is_active", "status")
    ordering = ("-start_datetime",)
    filter_horizontal = ()
    fieldsets = (
        ("General", {
            "fields": ("name", "description", "amount", "account", "tags", "is_balance_correction", "user",)
        }),
        ("Time & Recurrence", {
            "fields": ("start_datetime", "end_datetime", "duration_minutes", "recurrence")
        }),
        ("Status & Metadata", {
            "fields": ("is_active", "status", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ('id', 'date_range', 'status')
    list_filter = ('status',)
    search_fields = ('date_range',)


# ==========
# SchedulePattern: удобная форма
# ==========

DAY_CHOICES = (
    (DayType.WORK, "Рабочий"),
    (DayType.OFF, "Выходной"),
)

WEEK_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


class SchedulePatternForm(forms.ModelForm):
    """
    Удобная форма:
    - В режиме ALTERNATING редактируем pattern_text (строка "2,2,2,1")
    - В режиме WEEKDAY редактируем mon..sun как ChoiceField(work/off)
    """

    pattern_after_start = forms.JSONField(required=False, widget=forms.HiddenInput())
    weekday_map = forms.JSONField(required=False, widget=forms.HiddenInput())
    # Для ALTERNATING
    pattern_text = forms.CharField(
        label="Чередование блоков (через запятую)",
        required=False,
        help_text="Например: 2,2 или 2,1,2,2. Количество чисел должно быть чётным. "
                  "Начинаем с рабочих, затем выходные, и так далее."
    )

    # Для WEEKDAY
    mon = forms.ChoiceField(label="Понедельник", choices=DAY_CHOICES, required=False)
    tue = forms.ChoiceField(label="Вторник", choices=DAY_CHOICES, required=False)
    wed = forms.ChoiceField(label="Среда", choices=DAY_CHOICES, required=False)
    thu = forms.ChoiceField(label="Четверг", choices=DAY_CHOICES, required=False)
    fri = forms.ChoiceField(label="Пятница", choices=DAY_CHOICES, required=False)
    sat = forms.ChoiceField(label="Суббота", choices=DAY_CHOICES, required=False)
    sun = forms.ChoiceField(label="Воскресенье", choices=DAY_CHOICES, required=False)

    class Meta:
        model = SchedulePattern
        fields = [
            "name", "description",
            "mode",
            "days_off_at_start", "pattern_after_start",  # будут управляться через pattern_text
            "weekday_map",  # будет собираться из mon..sun
            "last_day_always_working",
            "working_day_duration",
        ]
        widgets = {
            # скроем «сырые» JSON-поля, мы их заполняем из удобных полей
            "pattern_after_start": forms.HiddenInput(),
            "weekday_map": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance = self.instance

        # Предзаполнение удобных полей
        if instance and instance.pk:
            if instance.mode == PatternMode.ALTERNATING:
                seq = instance.pattern_after_start or []
                if seq:
                    self.fields["pattern_text"].initial = ", ".join(str(int(x)) for x in seq)
            elif instance.mode == PatternMode.WEEKDAY:
                wm = instance.weekday_map or {}
                # разумный дефолт: будни — work, выхи — off
                defaults = {"mon": "work", "tue": "work", "wed": "work", "thu": "work", "fri": "work", "sat": "off",
                            "sun": "off"}
                data = {**defaults, **wm}
                for k in WEEK_KEYS:
                    self.fields[k].initial = data.get(k)

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")

        # Нормализуем данные по режимам
        if mode == PatternMode.ALTERNATING:
            # читаем pattern_text и превращаем в list[int]
            pattern_text = cleaned.get("pattern_text", "") or ""
            seq = []

            if pattern_text.strip():
                parts = [p.strip() for p in pattern_text.split(",")]
                try:
                    seq = [int(p) for p in parts]
                except Exception:
                    raise ValidationError(
                        {"pattern_text": "Можно вводить только целые положительные числа через запятую."})

                if any(x <= 0 for x in seq):
                    raise ValidationError({"pattern_text": "Все числа должны быть > 0."})

                if len(seq) % 2 != 0:
                    raise ValidationError(
                        {"pattern_text": "Количество чисел должно быть чётным (например, 2,2 или 2,1,2,2)."})

            if not seq:
                raise ValidationError({"pattern_text": "Нужно указать хотя бы один блок (например, 2,2)."})

            # записываем в скрытое JSON-поле
            cleaned["pattern_after_start"] = seq
            # WEEKDAY-поля «обнуляем»
            cleaned["weekday_map"] = None
            # days_off_at_start уже PositiveSmallIntegerField (>=0), ок

        elif mode == PatternMode.WEEKDAY:
            # Собираем карту дней недели
            wm = {}
            for k in WEEK_KEYS:
                v = cleaned.get(k)
                if v not in (DayType.WORK, DayType.OFF):
                    raise ValidationError({k: "Выберите 'Рабочий' или 'Выходной'."})
                wm[k] = v

            cleaned["weekday_map"] = wm
            # Эти поля должны быть пустыми в WEEKDAY-режиме
            cleaned["pattern_after_start"] = []
            if cleaned.get("days_off_at_start", 0) != 0:
                raise ValidationError({"days_off_at_start": "В режиме WEEKDAY значение должно быть равно 0."})

        # Вызовем модельную clean() для полной проверки
        try:
            self.instance.__dict__.update(cleaned)
            self.instance.clean()
        except ValidationError as e:
            raise e

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        mode = self.cleaned_data.get("mode")

        if mode == PatternMode.ALTERNATING:
            obj.weekday_map = None
            obj.pattern_after_start = self.cleaned_data.get("pattern_after_start") or []
        elif mode == PatternMode.WEEKDAY:
            obj.pattern_after_start = []
            obj.weekday_map = self.cleaned_data.get("weekday_map") or {}

        if commit:
            obj.save()
        return obj


@admin.register(SchedulePattern)
class SchedulePatternAdmin(admin.ModelAdmin):
    form = SchedulePatternForm

    list_display = (
        'name', 'mode', 'display_cycle', 'days_off_at_start',
        'working_day_duration', 'last_day_always_working'
    )
    list_filter = ('mode', 'last_day_always_working')
    search_fields = ('name',)

    def display_cycle(self, obj):
        # Показываем длину цикла только для ALTERNATING
        if obj.mode == PatternMode.ALTERNATING:
            return obj.cycle_length
        return "—"

    display_cycle.short_description = "Длина цикла"

    # Немного улучшим UX группировкой полей
    fieldsets = (
        ("Основное", {
            "fields": ("name", "description", "mode", "working_day_duration", "last_day_always_working")
        }),
        ("Чередование блоков (ALTERNATING)", {
            "fields": ("days_off_at_start", "pattern_text", "pattern_after_start"),
            "description": "Начинаем с рабочих, затем выходные, затем снова рабочие и т.д. "
                           "Пример: 2,2 или 2,1,2,2",
        }),
        ("По дням недели (WEEKDAY)", {
            "fields": ("mon", "tue", "wed", "thu", "fri", "sat", "sun", "weekday_map"),
            "description": "Каждый день недели задаётся как рабочий или выходной.",
        }),
    )


# ==========
# MonthSchedule: инлайн для DayOverride
# ==========

class DayOverrideInline(admin.TabularInline):
    model = DayOverride
    extra = 0
    fields = ("date", "type", "comment")
    ordering = ("date",)
    autocomplete_fields = ()
    show_change_link = True


@admin.register(MonthSchedule)
class MonthScheduleAdmin(admin.ModelAdmin):
    list_display = ('user', 'year', 'month', 'pattern')
    list_filter = ('year', 'month', 'pattern')
    search_fields = ('user__username',)
    autocomplete_fields = ('user', 'pattern')
    inlines = [DayOverrideInline]


@admin.register(DayOverride)
class DayOverrideAdmin(admin.ModelAdmin):
    list_display = ('month_schedule', 'date', 'type', 'comment')
    list_filter = ('type', 'date')
    search_fields = ('month_schedule__user__username', 'comment')
    autocomplete_fields = ('month_schedule',)
