from django.apps import AppConfig
from django.db.utils import OperationalError, ProgrammingError


class ScheduleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'schedule'

    def ready(self):
        """
        При старте приложения гарантируем, что шаблон 'Классика' существует.
        """
        try:
            from schedule.models import SchedulePattern, PatternMode
            SchedulePattern.objects.get_or_create(
                name="Классика",
                defaults={
                    "mode": PatternMode.WEEKDAY,
                    "days_off_at_start": 0,
                    "pattern_after_start": [],
                    "weekday_map": {
                        "mon": "work",
                        "tue": "work",
                        "wed": "work",
                        "thu": "work",
                        "fri": "work",
                        "sat": "off",
                        "sun": "off",
                    },
                    "description": "Пятидневка: Пн–Пт рабочие, Сб–Вс выходные.",
                }
            )
        except (OperationalError, ProgrammingError):
            # чтобы не падать при миграциях или при отсутствии таблиц
            pass
