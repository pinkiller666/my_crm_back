# --- файл: schedule/forms.py ---
from datetime import datetime, time
import calendar

from django import forms
from django.utils import timezone

from .models import Event
from accounting.models import Account


class EventAdminForm(forms.ModelForm):
    # 🔸 ВИРТУАЛЬНОЕ поле — живёт только в форме, в БД не пишется
    months_span = forms.IntegerField(
        label="На сколько месяцев",
        min_value=1,
        required=False,
        initial=1,
        help_text="Для повторяемых месячных событий: длина серии в месяцах (>=1)."
    )

    class Meta:
        model = Event
        fields = "__all__"
        widgets = {
            "tags": forms.TextInput(attrs={
                "style": "width:100%",
                "placeholder": "tag1, tag2, tag3",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # --- Фильтрация аккаунтов по выбранному пользователю (если нужно) ---
        selected_user_id = None
        if self.data and self.data.get("user"):
            selected_user_id = self.data.get("user")
        elif self.instance and getattr(self.instance, "user_id", None):
            selected_user_id = self.instance.user_id
        elif self.initial.get("user"):
            selected_user_id = self.initial["user"]

        if selected_user_id and "account" in self.fields:
            try:
                self.fields["account"].queryset = Account.objects.filter(user_id=selected_user_id)
            except Exception:
                pass

        # --- Разумные дефолты для месячного режима ---
        if (self.initial.get("date_mode") == "number_of_month" or
                (self.instance and getattr(self.instance, "date_mode", None) == "number_of_month")):
            now = timezone.localtime()
            self.initial.setdefault("month_year", now.year)
            self.initial.setdefault("month_number", now.month)
            self.initial.setdefault("month_interval", 1)
            self.initial.setdefault("months_span", 1)

    # --- помощники для вычисления дат ---
    @staticmethod
    def _add_months(year: int, month: int, delta: int) -> (int, int):
        """Вернуть (year, month) спустя delta месяцев от (year, month)."""
        m = month - 1 + delta
        y = year + m // 12
        m = m % 12 + 1
        return y, m

    @staticmethod
    def _last_day_of_month(year: int, month: int) -> int:
        return calendar.monthrange(year, month)[1]

    def clean(self):
        cleaned = super().clean()

        date_mode = cleaned.get("date_mode")
        is_recurring_monthly = cleaned.get("is_recurring_monthly") is True
        month_year = cleaned.get("month_year")
        month_number = cleaned.get("month_number")

        # months_span из формы: по умолчанию 1
        months_span = cleaned.get("months_span") or 1
        if months_span < 1:
            months_span = 1

        # Применяем только для МЕСЯЦ + ПОВТОР
        if date_mode == "number_of_month" and is_recurring_monthly:
            if not (isinstance(month_year, int) and isinstance(month_number, int) and 1 <= month_number <= 12):
                raise forms.ValidationError("Для месячного режима укажите корректные 'month_year' и 'month_number'.")

            # --- START: 20 число ПРЕДЫДУЩЕГО месяца, 00:00:00 (локальная TZ), включительно ---
            prev_year, prev_month = self._add_months(month_year, month_number, -1)
            start_naive = datetime(prev_year, prev_month, 20, 0, 0, 0)
            start_dt = timezone.make_aware(start_naive, timezone.get_current_timezone())

            # --- END: последний день (month_year, month_number) + (months_span-1), 23:59:59, включительно ---
            end_year, end_month = self._add_months(month_year, month_number, months_span - 1)
            last_day = self._last_day_of_month(end_year, end_month)
            end_naive = datetime.combine(
                datetime(end_year, end_month, last_day).date(),
                time(23, 59, 59)
            )
            end_dt = timezone.make_aware(end_naive, timezone.get_current_timezone())

            cleaned["start_datetime"] = start_dt
            cleaned["end_datetime"] = end_dt

            # Между делом: для повторяемых месячных событий шаг по умолчанию = 1
            cleaned.setdefault("month_interval", 1)

        return cleaned
