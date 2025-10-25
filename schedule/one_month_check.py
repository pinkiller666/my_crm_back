from datetime import datetime, timedelta


class NoFullMonthError(Exception):
    """Ошибка: В диапазоне нет полностью покрытого месяца."""
    pass


class MultipleFullMonthsError(Exception):
    """Ошибка: В диапазоне больше одного полного месяца."""
    pass


def get_main_month(start_dt: datetime, end_dt: datetime):
    """
    Определяет, какой месяц входит в диапазон start_dt - end_dt целиком.
    Проверяет, что в диапазоне максимум 1 полный месяц.
    """
    # Получаем первый день текущего месяца
    first_day_current_month = start_dt.replace(day=1)

    # Получаем первый день следующего месяца
    first_day_next_month = (first_day_current_month + timedelta(days=32)).replace(day=1)

    # Получаем последний день текущего месяца
    last_day_current_month = first_day_next_month - timedelta(days=1)

    # Проверяем, полностью ли покрыт текущий месяц
    full_months = []
    if first_day_current_month >= start_dt and last_day_current_month <= end_dt:
        full_months.append((first_day_current_month.year, first_day_current_month.month))

    # Двигаемся дальше, если start_dt далеко до конца диапазона
    next_month = first_day_next_month
    while next_month < end_dt:
        first_day_next = next_month
        last_day_next = (first_day_next + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        if first_day_next >= start_dt and last_day_next <= end_dt:
            full_months.append((first_day_next.year, first_day_next.month))

        next_month = (first_day_next + timedelta(days=32)).replace(day=1)  # Переход на следующий месяц

    # Ошибка: нет ни одного полного месяца
    if not full_months:
        raise NoFullMonthError("В данном диапазоне нет полностью покрытого месяца.")

    # Ошибка: больше одного полного месяца
    if len(full_months) > 1:
        raise MultipleFullMonthsError(f"В данном диапазоне содержится более одного полного месяца: {full_months}")

    # Если все ОК, возвращаем единственный найденный месяц
    year, month = full_months[0]
    return {
        "year": year,
        "month": month,
    }
