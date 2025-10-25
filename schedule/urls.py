from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.views.i18n import JavaScriptCatalog

from .views import (
    schedule_preview, EventExpandedListView,
    EventViewSet, EventInstanceViewSet, SlotViewSet,
    SchedulePatternViewSet, MonthScheduleViewSet, DayOverrideViewSet, DeleteEventOrOccurrenceView, UpdateOccurrenceStatusView
)

router = DefaultRouter()
router.register(r'events', EventViewSet)
router.register(r'instances', EventInstanceViewSet)
router.register(r'slots', SlotViewSet)
router.register(r'patterns', SchedulePatternViewSet)
router.register(r'month-schedules', MonthScheduleViewSet)
router.register(r'day-overrides', DayOverrideViewSet)


urlpatterns = [

    path('all_events/', EventExpandedListView.as_view(), name='events-expanded'),
    # Schedule & Tasks
    path('preview/', schedule_preview, name='schedule-preview'),

    path('events/<int:event_id>/delete/', DeleteEventOrOccurrenceView.as_view()),
    path('events/<int:event_id>/update-status/', UpdateOccurrenceStatusView.as_view()),


    # Internationalization
    path('jsi18n.js', JavaScriptCatalog.as_view(packages=['recurrence']), name='jsi18n'),

    # ViewSets (DRF)
    path('', include(router.urls)),
]


# Удалить root событие    DELETE  /events/5/delete/   —
# Удалить occurrence  DELETE  /events/5/delete/?instance_datetime=2025-08-07T14:00:00Z    —
# Обновить статус occurrence  PATCH   /events/5/update-status/    { "instance_datetime": "2025-08-07T14:00:00Z", "status": "complete" }
