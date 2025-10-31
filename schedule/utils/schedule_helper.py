from datetime import date, timedelta
from typing import List, Tuple
import calendar

from schedule.models import PatternMode


# ------------------------------------------------------------
# 🔹 Вспомогательная функция для получения ключа дня недели
# ------------------------------------------------------------
def _weekday_key(d) -> str:
    """Возвращает ключ 'mon'..'sun' по числу weekday(), без зависимости от локали."""
    keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    return keys[d.weekday()]


# ------------------------------------------------------------
# 🔹 Основная логика генерации типов дней
# ------------------------------------------------------------
def _generate_day_types_core(start_date: date, days_in_month: int, pattern) -> List[str]:
    """
    Возвращает список типов дней ('work', 'off', ...) длиной days_in_month.
    Используется обеими обёртками: для schedule и для прямого вызова.
    """
    if days_in_month <= 0:
        return []

    # === Ветка 1: режим WEEKDAY ==============================================
    if pattern.mode == PatternMode.WEEKDAY:
        weekday_map = getattr(pattern, "weekday_map", None)
        if not weekday_map:
            raise ValueError(
                "SchedulePattern.weekday_map пуст для режима WEEKDAY — заполните карту дней недели."
            )

        required_keys = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        missing = required_keys.difference(set(weekday_map.keys()))
        if missing:
            raise ValueError(f"В weekday_map отсутствуют ключи: {', '.join(sorted(missing))}.")

        result: List[str] = []
        for i in range(days_in_month):
            day_date = start_date + timedelta(days=i)
            key = _weekday_key(day_date)
            day_type = weekday_map.get(key)
            if day_type is None:
                raise ValueError(f"В weekday_map отсутствует ключ '{key}' для режима WEEKDAY.")
            result.append(day_type)
        return result

    # === Ветка 2: режим ALTERNATING ==========================================
    pattern_list = pattern.pattern_after_start or []
    if not pattern_list:
        raise ValueError(
            "pattern_after_start пуст для режима ALTERNATING. "
            "Заполните список (например, [2,2] или [5,2,2])."
        )

    result: List[str] = []

    # 1) Блок выходных в начале
    days_off_at_start = getattr(pattern, "days_off_at_start", 0) or 0
    for _ in range(min(days_off_at_start, days_in_month)):
        result.append("off")

    # 2) Основной цикл блоков (чередование work/off)
    block_index = 0
    is_work_block = True  # стартуем с рабочих после начальных выходных

    while len(result) < days_in_month:
        raw_value = pattern_list[block_index]
        try:
            block_len = int(raw_value)
        except (TypeError, ValueError):
            raise ValueError(f"Элемент pattern_after_start[{block_index}] = {raw_value!r} не число.")
        if block_len <= 0:
            raise ValueError(f"Длина блока должна быть > 0 (ошибка в позиции {block_index + 1}).")

        label = "work" if is_work_block else "off"
        for _ in range(block_len):
            if len(result) >= days_in_month:
                break
            result.append(label)

        is_work_block = not is_work_block
        block_index = (block_index + 1) % len(pattern_list)

    return result


# ------------------------------------------------------------
# 🔹 Группировка по шаблону (ALTERNATING) или неделям (WEEKDAY)
# ------------------------------------------------------------
def _return_groups_core(start_date: date, days_in_month: int, pattern) -> Tuple[List[int], List[str]]:
    """Возвращает (список_длин_групп, список_лейблов_на_группу)."""
    if days_in_month <= 0:
        return [], []

    # === Ветка WEEKDAY =======================================================
    if pattern.mode == PatternMode.WEEKDAY:
        groups: List[int] = []
        labels: List[str] = []

        # Python: Monday=0, ..., Sunday=6
        start_wd = start_date.weekday()
        remaining = days_in_month

        # Первая группа: до ближайшего воскресенья
        first_group = 7 - start_wd if start_wd != 0 else 7
        first_group = min(first_group, remaining)

        if first_group > 0:
            groups.append(first_group)
            labels.append("week")
            remaining -= first_group

        # Полные недели
        while remaining >= 7:
            groups.append(7)
            labels.append("week")
            remaining -= 7

        # Хвост
        if remaining > 0:
            groups.append(remaining)
            labels.append("week")

        return groups, labels

    # === Ветка ALTERNATING ===================================================
    day_types = _generate_day_types_core(start_date, days_in_month, pattern)
    if not day_types:
        return [], []

    groups: List[int] = []
    labels: List[str] = []

    current_label = day_types[0]
    current_len = 1

    for label in day_types[1:]:
        if label == current_label:
            current_len += 1
        else:
            groups.append(current_len)
            labels.append(current_label)
            current_label = label
            current_len = 1

    groups.append(current_len)
    labels.append(current_label)
    return groups, labels


# ------------------------------------------------------------
# 🔹 Удобные публичные обёртки для MonthSchedule
# ------------------------------------------------------------
def generate_day_types(schedule_or_date, days_in_month: int = None, pattern=None) -> List[str]:
    """
    Универсальная функция:
      • Если передан MonthSchedule → вычисляет все параметры сама.
      • Если переданы start_date + days_in_month + pattern → работает напрямую.
    """
    # режим 1: передан MonthSchedule
    if hasattr(schedule_or_date, "year") and hasattr(schedule_or_date, "month"):
        schedule = schedule_or_date
        pattern = schedule.pattern
        start_date = date(schedule.year, schedule.month, 1)
        _, days_in_month = calendar.monthrange(schedule.year, schedule.month)
    else:
        start_date = schedule_or_date
        if days_in_month is None or pattern is None:
            raise ValueError("Необходимо указать days_in_month и pattern при прямом вызове.")
    return _generate_day_types_core(start_date, days_in_month, pattern)


def return_groups_by_pattern(schedule_or_date, days_in_month: int = None, pattern=None) -> Tuple[List[int], List[str]]:
    """
    Универсальная функция:
      • Если передан MonthSchedule → вычисляет все параметры сама.
      • Если переданы start_date + days_in_month + pattern → работает напрямую.
    """
    if hasattr(schedule_or_date, "year") and hasattr(schedule_or_date, "month"):
        schedule = schedule_or_date
        pattern = schedule.pattern
        start_date = date(schedule.year, schedule.month, 1)
        _, days_in_month = calendar.monthrange(schedule.year, schedule.month)
    else:
        start_date = schedule_or_date
        if days_in_month is None or pattern is None:
            raise ValueError("Необходимо указать days_in_month и pattern при прямом вызове.")
    return _return_groups_core(start_date, days_in_month, pattern)
