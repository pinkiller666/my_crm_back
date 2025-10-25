from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum

from django.db.models import Case, When, Value, BooleanField

from artworks.models import Commission, Artist, Artwork
from identity.models import Middleman
from common.choices import currency_choices

User = get_user_model()


class Account(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="accounts",
    )

    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_primary=True),
                name="unique_primary_account_per_user",
            ),
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_account_name_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_primary"]),
            models.Index(fields=["user", "name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.user})"

    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        Гарантируем «ровно один primary» одним UPDATE ... CASE:
        - Для нового объекта: сначала сохраняем с is_primary=False, чтобы получить pk,
          затем одним апдейтом делаем this=True, others=False.
        - Для существующего: сразу выполняем CASE-апдейт.
        - Если это первый счёт пользователя — автоматически делаем его primary.
        """
        print('ПЕНИС')
        want_primary = bool(self.is_primary)
        is_new = self.pk is None
        print(want_primary, is_new)

        # Если это первый счёт юзера — даже если галочку не ставили, делаем primary
        if is_new and not want_primary:
            if not Account.objects.filter(user=self.user).exists():
                want_primary = True

        if is_new:
            # ВАЖНО: сохраняем впервые с is_primary=False, чтобы не нарушить unique до массового апдейта
            self.is_primary = False
            super().save(*args, **kwargs)  # теперь у нас есть self.pk

        if want_primary:
            # Один атомарный апдейт: этому счёту True, всем остальным False
            print('updating')
            Account.objects.filter(user=self.user).update(
                is_primary=False
            )
            Account.objects.filter(pk=self.pk).update(is_primary=True)
            # self.is_primary = True
        else:
            # Обычное сохранение без переключения primary
            super().save(*args, **kwargs)
            # Страховка «не ноль primary»: если вдруг не осталось ни одного — сделаем текущий primary
            if not Account.objects.filter(user=self.user, is_primary=True).exists():
                Account.objects.filter(user=self.user).update(
                    is_primary=Case(
                        When(pk=self.pk, then=Value(True)),
                        default=Value(False),
                        output_field=BooleanField(),
                    )
                )
                self.is_primary = True



    @transaction.atomic
    def delete(self, *args, **kwargs):
        """
        Если удаляем primary — назначаем другой счёт primary (если есть).
        """
        user = self.user
        was_primary = self.is_primary
        super().delete(*args, **kwargs)

        if was_primary:
            other = Account.objects.filter(user=user).order_by("created_at").first()
            if other and not other.is_primary:
                other.is_primary = True
                other.save()

    @property
    def balance(self):
        total = self.events.filter(
            is_active=True,
            amount__isnull=False,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return total


class Payment(models.Model):
    PAY_SYSTEM_CHOICES = [
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    order = models.ForeignKey(Commission, on_delete=models.CASCADE, related_name="payments")
    middleman = models.ForeignKey(Middleman, on_delete=models.SET_NULL, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=currency_choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    pay_system = models.CharField(max_length=50, choices=PAY_SYSTEM_CHOICES)

    payment_screenshot = models.ImageField(
        upload_to='payment_screenshots/',
        null=True,
        blank=True,
        help_text='Загрузите скриншот подтверждения оплаты',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for {self.order}, {self.amount} {self.currency}"


class Payout(models.Model):
    PAYOUT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
    ]

    middleman = models.ForeignKey(Middleman, on_delete=models.CASCADE)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="payouts")
    orders = models.ManyToManyField(Artwork)
    status = models.CharField(max_length=50, choices=PAYOUT_STATUS_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payments = models.ManyToManyField(Payment)
    currency = models.CharField(max_length=3, choices=currency_choices)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payout {self.status} for {self.artist.name} of {self.amount} {self.orders.count()} orders"


class FinancialEntry(models.Model):
    entry_type_choices = [
        ('earn', 'Приход денег'),
        ('spend', 'Трата денег'),
        ('withdraw', 'Вывод денег'),
    ]

    year = models.IntegerField()
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="financial_entries",
    )

    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="financial_entries",
        null=True, blank=True
    )

    currency = models.CharField(max_length=3, choices=currency_choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    entry_type = models.CharField(max_length=20, choices=entry_type_choices)
    local_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "year", "month"]),
            models.Index(fields=["account", "year", "month"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "account", "year", "month", "entry_type", "currency"],
                name="uniq_fin_entry_bucket",
            )
        ]

    def clean(self):
        if self.account_id and self.user_id and self.account.user_id != self.user_id:
            raise ValidationError({"account": "Нельзя выбрать счёт, который не принадлежит этому пользователю."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
