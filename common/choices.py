from django.db import models

currency_choices = [
    ('USD', 'USD'),
    ('RUB', 'RUB'),
    ('EUR', 'EUR'),
    ('KZT', 'KZT'),  # Казахстанский тенге
]


class SocialMediaChoices(models.TextChoices):
    """Общие типовые соцсети для ArtistContact, CommissionerContact и др."""
    TELEGRAM = 'telegram', 'Telegram'
    DISCORD = 'discord', 'Discord'
    TWITTER = 'twitter', 'Twitter (X)'
    BLUESKY = 'bluesky', 'Bluesky'
    INSTAGRAM = 'instagram', 'Instagram'
    EMAIL = 'email', 'Email'
    OTHER = 'other', 'Другое'


class DayType(models.TextChoices):
    WORK = 'work', 'Рабочий'
    OFF = 'off', 'Выходной'
    VACATION = 'vacation', 'Отпуск'
    SICK = 'sick', 'Болезнь'


class EventDateMode(models.TextChoices):
    EXACT_DATE = 'exact_date', 'Точная дата'  # текущая логика (start_datetime / recurrence)
    NUMBER_OF_MONTH = 'number_of_month', 'нормер месяца'  # «коммуналка за месяц»
    NUMBER_OF_WEEK = 'number_of_week', 'N-я неделя'  # опц.: 2-я пятница и т.п.


# БЭК | common/choices.py
class RecurrenceType(models.TextChoices):
    SINGLE = 'single', 'Single'
    MONTHLY = 'monthly', 'Monthly'
    RRULE = 'rrule', 'RRULE'
