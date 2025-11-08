from rest_framework import serializers
from .models import (
    Event, EventInstance, Slot,
    SchedulePattern, MonthSchedule, DayOverride
)
from identity.serializers import UserSerializer


class EventSerializer(serializers.ModelSerializer):
    # ——— Переименованные поля дат для фронта
    starts_at = serializers.DateTimeField(source="start_datetime", required=False)
    ends_at = serializers.DateTimeField(source="end_datetime", allow_null=True, required=False)

    # ——— Упрощённые идентификаторы, без вложенных объектов
    account_id = serializers.IntegerField(allow_null=True, required=False)
    user_id = serializers.IntegerField(read_only=True, source="user_id")

    # ——— Виртуальные/вычисляемые поля
    rrule = serializers.SerializerMethodField()
    rrule_exceptions = serializers.SerializerMethodField()
    is_recurring = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            # базовые
            "id",
            "event_type",
            "category",
            "type",
            "name",
            "description",

            # даты/время
            "starts_at",
            "ends_at",
            "all_day",
            "timezone",

            # повторяемость
            "rrule",
            "rrule_exceptions",
            "is_recurring",
            "date_mode",
            "is_recurring_monthly",
            "month_interval",

            # деньги/счета/статусы
            "account_id",
            "amount",
            "currency",  # если есть в модели
            "status",
            "is_active",
            "is_completed",
            "is_balance_correction",

            # прочее
            "tags",
            "meta",  # 👈 тут теперь есть запятая
            "duration_minutes",
            "month_year",
            "month_number",
            "date_day",
            "user_id",
        )

    # ——— Методы для виртуальных полей
    def get_rrule(self, obj):
        # RecurrenceField → строка; если пусто — None
        return str(obj.recurrence) if getattr(obj, "recurrence", None) else None

    def get_rrule_exceptions(self, obj):
        # пока исключений нет — фронту стабильно возвращаем список
        return []

    def get_is_recurring(self, obj):
        # true, если есть rrule или твой флаг ежемесячной повторяемости
        has_rrule = bool(getattr(obj, "recurrence", None))
        has_monthly = bool(getattr(obj, "is_recurring_monthly", False))
        return has_rrule or has_monthly


class EventInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventInstance
        fields = '__all__'

    def validate_event(self, value):
        """Гарантия, что выбирается только свой Event (удобно для DRF Browsable API)."""
        request = self.context.get("request")
        if request is None:
            return value
        if value.user != request.user:
            raise serializers.ValidationError("Select your own event only.")
        return value


class SlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slot
        fields = '__all__'


class SchedulePatternSerializer(serializers.ModelSerializer):
    cycle_length = serializers.IntegerField(read_only=True)

    class Meta:
        model = SchedulePattern
        fields = (
            'id', 'name', 'description',
            'mode', 'weekday_map',
            'days_off_at_start', 'pattern_after_start',
            'last_day_always_working', 'working_day_duration',
            'cycle_length'
        )


class MonthScheduleSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = MonthSchedule
        fields = '__all__'


class DayOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = DayOverride
        fields = '__all__'
