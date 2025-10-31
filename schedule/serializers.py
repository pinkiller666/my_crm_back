from rest_framework import serializers
from .models import (
    Event, EventInstance, Slot,
    SchedulePattern, MonthSchedule, DayOverride
)
from identity.serializers import UserSerializer


class EventSerializer(serializers.ModelSerializer):
    starts_at = serializers.DateTimeField(source='start_datetime')
    ends_at = serializers.DateTimeField(source='end_datetime')
    rrule = serializers.CharField(source='recurrence', allow_blank=True, allow_null=True)
    rrule_exceptions = serializers.ListField(
        child=serializers.DateField(format='%Y-%m-%d'),
        source='recurrence_exceptions',
        required=False
    )
    account_id = serializers.IntegerField(source='account_id', allow_null=True)

    class Meta:
        model = Event
        fields = (
            'id', 'event_type', 'category', 'type', 'name', 'description',
            'starts_at', 'ends_at', 'all_day', 'timezone',
            'rrule', 'rrule_exceptions',
            'account_id', 'amount', 'currency',
            'status', 'is_active', 'is_balance_correction',
            'tags', 'meta'
        )

    def get_is_recurring(self, obj):
        return bool(obj.recurrence)


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
