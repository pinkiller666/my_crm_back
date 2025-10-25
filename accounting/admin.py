from django.contrib import admin, messages
from .models import Account, Payment, Payout, FinancialEntry
from django.db import transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "balance", "is_archived", "created_at", "updated_at")
    search_fields = ("name", "user__username", "user__email")
    list_filter = ("is_archived", "user")
    ordering = ("-created_at",)
    actions = ["make_primary"]  # ← важно: явно регистрируем экшен

    @admin.action(description="Сделать выбранный аккаунт primary")
    def make_primary(self, request, queryset):
        # Разрешаем выделять только 1 запись (иначе смысла нет)
        if queryset.count() != 1:
            self.message_user(request, "Выберите ровно один аккаунт.", level=messages.ERROR)
            return
        acc = queryset.first()
        with transaction.atomic():
            acc.is_primary = True
            acc.save()  # сработают сигналы: у остальных станет False
        self.message_user(request, f"Аккаунт «{acc.name}» назначен primary.", level=messages.SUCCESS)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'middleman', 'amount', 'currency', 'pay_system')
    list_filter = ('pay_system', 'middleman', 'currency')
    search_fields = ('order__id', 'order__artist__name', 'middleman__name')


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ('id', 'middleman', 'artist', 'status', 'amount', 'total_orders')  # ← добавили total_orders
    list_filter = ('status', 'middleman', 'artist')
    search_fields = ('middleman__name', 'artist__name')
    filter_horizontal = ('orders', 'payments')

    def total_orders(self, obj):
        return obj.orders.count()
    total_orders.short_description = "Total Artworks"


@admin.register(FinancialEntry)
class FinancialEntryAdmin(admin.ModelAdmin):
    # 🛠️ фикс запятой + добавил amount/currency (удобно)
    list_display = ('user', 'account', 'year', 'month', 'entry_type', 'amount', 'currency', 'local_amount')
    list_filter = ('user', 'account', 'entry_type', 'currency', 'year', 'month')
    search_fields = ('user__username', 'user__email', 'account__name')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "account":
            user_id = request.GET.get("user") or request.POST.get("user")
            if user_id:
                kwargs["queryset"] = Account.objects.filter(user_id=user_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
