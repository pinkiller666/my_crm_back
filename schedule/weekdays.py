from typing import Union


class Weekday:
    _days_full = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    _days_short = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    _days_full_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    _days_short_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    # Приводим все ключи в нижний регистр (lower()), чтобы не учитывать регистр
    _day_synonyms = {key.lower(): value for key, value in {
        # Понедельник
        "1": 1, "Monday": 1, "Mon": 1, "Понедельник": 1, "Пн": 1,

        # Вторник
        "2": 2, "Tuesday": 2, "Tue": 2, "Вторник": 2, "Вт": 2,

        # Среда
        "3": 3, "Wednesday": 3, "Wed": 3, "Среда": 3, "Ср": 3,

        # Четверг
        "4": 4, "Thursday": 4, "Thu": 4, "Четверг": 4, "Чт": 4,

        # Пятница
        "5": 5, "Friday": 5, "Fri": 5, "Пятница": 5, "Пт": 5,

        # Суббота
        "6": 6, "Saturday": 6, "Sat": 6, "Суббота": 6, "Сб": 6,

        # Воскресенье
        "7": 7, "Sunday": 7, "Sun": 7, "Воскресенье": 7, "Вс": 7,
    }.items()}

    @staticmethod
    def get_day_number(day_input: Union[int, str]) -> int:
        """
        Возвращает номер дня недели (1-7) по названию дня или самому номеру.

        :param day_input: Название дня недели (строка) или номер дня (число 1-7).
        :return: Число от 1 до 7, соответствующее дню недели.
        :raises ValueError: Если входные данные некорректны.
        """
        # Если вход - строка, которая может быть числом
        if isinstance(day_input, str) and day_input.isdigit():
            day_input = int(day_input)

        # Если вход - число, проверяем диапазон
        if isinstance(day_input, int):
            if 1 <= day_input <= 7:
                return day_input
            raise ValueError(f"Число '{day_input}' вне диапазона 1-7.")

        # Если вход - строка, приводим к нижнему регистру перед поиском
        if isinstance(day_input, str):
            day_input = day_input.strip().lower()  # убираем пробелы и приводим к нижнему регистру
            day_number = Weekday._day_synonyms.get(day_input)

            if day_number is not None:
                return day_number

        raise ValueError(f"Некорректный ввод: '{day_input}'. Ожидалось число 1-7 или строка с названием дня.")

    @staticmethod
    def get_day_by_number(day_number: Union[int, str], format_type: str = "full_EN") -> str:
        """
        Возвращает название дня недели по номеру (1-7) в указанном формате.

        :param day_number: Номер дня недели (1 - Понедельник, 7 - Воскресенье). Может быть строкой или числом.
        :param format_type: Формат возвращаемого дня недели:
            - "full_EN"  -> Полное название на английском (Monday, ...)
            - "short_EN" -> Сокращённое название на английском (Mon, ...)
            - "full_RU"  -> Полное название на русском (Понедельник, ...)
            - "short_RU" -> Сокращённое название на русском (Пн, ...)
        :return: Название дня недели в указанном формате.
        :raises ValueError: Если номер дня или формат недопустим.
        """
        if isinstance(day_number, str):
            if day_number.isdigit() and 1 <= int(day_number) <= 7:
                day_number = int(day_number)
            else:
                raise ValueError(f"Некорректный номер дня недели: '{day_number}'. Ожидалось число от 1 до 7.")

        if isinstance(day_number, int):
            if not 1 <= day_number <= 7:
                raise ValueError(f"Номер дня недели должен быть в диапазоне от 1 до 7: {day_number}.")
        else:
            raise ValueError(f"Некорректный тип данных: {type(day_number)}. Ожидалось int или str.")

        format_map = {
            "full_EN": Weekday._days_full,
            "short_EN": Weekday._days_short,
            "full_RU": Weekday._days_full_RU,
            "short_RU": Weekday._days_short_RU,
        }

        if format_type not in format_map:
            raise ValueError(f"Недопустимый формат: {format_type}. Возможные значения: {list(format_map.keys())}")

        return format_map[format_type][day_number - 1]
