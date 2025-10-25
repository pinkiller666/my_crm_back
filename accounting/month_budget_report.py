from .models import FinancialEntry
from decimal import Decimal
from django.db.models import Sum
from datetime import datetime
from django.utils import timezone
from schedule.models import Event, CompletionStatus
import calendar


def get_rate(user, year, month, currency):
    latest_entry = FinancialEntry.objects.filter(
        user=user,
        year=year,
        month=month,
        entry_type="withdraw",
        currency=currency
    ).order_by('-id').first()

    if latest_entry:
        return latest_entry.local_amount / latest_entry.amount

    default_rates = {
        'rub': Decimal('1'),
        'usd': Decimal('72'),
        'eur': Decimal('80')
    }

    return default_rates.get(currency, Decimal('0'))


def planned_finances_month(user, month: int, year: int, tz=None):
    """
    Считает планируемые финансы за месяц.
    Возвращает объект { "earn": сумма доходов (>0), "spend": сумма расходов (<0) }.
    """
    if tz is None:
        tz = timezone.get_current_timezone()

    # границы месяца
    start_dt = datetime(year, month, 1, tzinfo=tz)
    last_day = calendar.monthrange(year, month)[1]
    end_dt = datetime(year, month, last_day, 23, 59, 59, tzinfo=tz)

    earn = 0
    spend = 0

    # Берём все активные события без фильтра по start_datetime
    events = Event.objects.filter(
        user=user,
        is_active=True,
        is_balance_correction=False
    ).exclude(status=CompletionStatus.CANCELLED)

    print(events)

    for event in events:
        # --- одноразовые события ---
        if not event.recurrence:
            if start_dt <= event.start_datetime <= end_dt:
                if event.amount:
                    if event.amount > 0:
                        earn += event.amount
                    elif event.amount < 0:
                        spend += event.amount

        # --- повторяющиеся события ---
        else:
            occurrences = event.get_occurrences(start_dt, end_dt, tz)
            for occ in occurrences:
                if occ.amount:
                    if occ.amount > 0:
                        earn += occ.amount
                    elif occ.amount < 0:
                        spend += occ.amount

    return {
        "earn": float(earn),
        "spend": float(spend),
    }


def get_complete_report(user, month, year):
    all_currencies = [code for code, _ in FinancialEntry.currency_choices]

    rates = {
        currency: get_rate(user, year, month, currency)
        for currency in all_currencies
    }

    total_income_rub = Decimal('0')
    total_withdraw_rub = Decimal('0')

    # Группировка доходов по валютам
    earn_entries_by_currency = FinancialEntry.objects.filter(
        user=user,
        month=month,
        year=year,
        entry_type="earn"
    ).values('currency').annotate(total=Sum('amount'))

    for item in earn_entries_by_currency:
        currency = item['currency']
        amount = item['total'] or Decimal('0')
        rate = rates.get(currency, Decimal('0'))
        total_income_rub += amount * rate

    # Группировка выводов по валютам
    withdraw_entries_by_currency = FinancialEntry.objects.filter(
        user=user,
        month=month,
        year=year,
        entry_type="withdraw"
    ).values('currency').annotate(total=Sum('amount'))

    for item in withdraw_entries_by_currency:
        currency = item['currency']
        amount = item['total'] or Decimal('0')
        rate = rates.get(currency, Decimal('0'))
        total_withdraw_rub += amount * rate

    remaining_rub = total_income_rub - total_withdraw_rub

    return {
        'total_income_rub': total_income_rub,
        'total_withdraw_rub': total_withdraw_rub,
        'remaining_rub': remaining_rub,
        'rates': rates,  # {'usd': Decimal(...), ...}
        'planned': planned_finances_month(user, month, year)
    }
