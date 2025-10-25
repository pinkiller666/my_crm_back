from calendar import monthrange
from datetime import date, timedelta
from typing import List, Tuple

from schedule.models import MonthSchedule, DayType, SchedulePattern


def generate_day_types(schedule: MonthSchedule) -> List[Tuple[date, str]]:
    """
    Генерирует список (дата, тип_дня) для данного расписания месяца
    без учёта исключений.
    """
    year = schedule.year
    month = schedule.month
    pattern = schedule.pattern

    _, days_in_month = monthrange(year, month)
    result = []
    current_day = date(year, month, 1)

    # 1. Первые N дней — выходные
    for _ in range(pattern.days_off_at_start):
        if current_day.month != month:
            break
        result.append((current_day, DayType.OFF))
        current_day += timedelta(days=1)

    # 2. Чередование по pattern_after_start
    pattern_list = pattern.pattern_after_start or []
    pattern_index = 0
    work = True  # начинаем с рабочих, если [2, 2]

    while current_day.month == month:
        count = pattern_list[pattern_index % len(pattern_list)]
        for _ in range(count):
            if current_day.month != month:
                break
            result.append((current_day, DayType.WORK if work else DayType.OFF))
            current_day += timedelta(days=1)
        pattern_index += 1
        work = not work

    # 3. Последний день месяца — всегда рабочий
    if pattern.last_day_always_working:
        last_day = date(year, month, days_in_month)
        result = [
            (d, DayType.WORK if d == last_day else t)
            for (d, t) in result
        ]

    return result


def return_groups_by_pattern(schedule: MonthSchedule) -> List[int]:
    """
    Возвращает список размеров групп дней на основе шаблона месяца без детализации по типам дней.
    Используется для визуальной группировки дней на фронте.

    Пример:
        [7, 10, 10, 3, 1] означает:
        - 7 выходных в начале,
        - 2 цикла по 10 дней (например, 5/5),
        - остаток 3 дня,
        - и 1 день, если последний принудительно рабочий и должен быть отделён.
    """
    year = schedule.year
    month = schedule.month
    pattern = schedule.pattern

    _, days_in_month = monthrange(year, month)
    result: List[int] = []

    # 1. Группа выходных в начале
    days_off_at_start = pattern.days_off_at_start
    result.append(days_off_at_start)

    # 2. Оставшиеся дни после выходных
    remaining = days_in_month - days_off_at_start

    # 3. Циклы по pattern_after_start (например, [5, 5] = 10)
    pattern_list = pattern.pattern_after_start or []
    pattern_total = sum(pattern_list)

    while remaining >= pattern_total:
        result.append(pattern_total)
        remaining -= pattern_total

    # 4. Остаток до конца месяца (временно)
    if remaining > 0:
        result.append(remaining)

    # 5. Обработка последнего рабочего дня
    if pattern.last_day_always_working:
        # Последний день месяца
        last_day_index = sum(result) - 1
        if last_day_index + 1 == days_in_month:
            # Если последний день в составе группы
            if days_in_month > 1:
                previous_day_index = last_day_index - 1
                total_days_before_last_group = sum(result[:-1])
                if result[-1] == 1:
                    # Только один день в последней группе — точно отделяем
                    result[-1] = 0
                    result.append(1)
                elif result[-1] >= 2 and previous_day_index < total_days_before_last_group + result[-1] - 1:
                    # Проверяем, нужно ли отделять по типу — тут нет типов, отделяем по соглашению
                    result.append(1)
                    result[-2] -= 1

    # Убираем пустые нули
    result = [r for r in result if r > 0]
    return result
