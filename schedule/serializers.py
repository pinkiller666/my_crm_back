from rest_framework import serializers
from .models import (
    Event, EventInstance, Slot,
    SchedulePattern, MonthSchedule, DayOverride
)
from identity.serializers import UserSerializer


class EventSerializer(serializers.ModelSerializer):
    is_recurring = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = '__all__'

    def get_is_recurring(self, obj):
        return bool(obj.recurrence)


class EventInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventInstance
        fields = '__all__'


class SlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slot
        fields = '__all__'


class SchedulePatternSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchedulePattern
        fields = '__all__'


class MonthScheduleSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = MonthSchedule
        fields = '__all__'


class DayOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = DayOverride
        fields = '__all__'
