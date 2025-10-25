from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from schedule.models import Slot
from identity.models import Artist, Commissioner
from django.contrib.auth import get_user_model
from common.choices import currency_choices

User = get_user_model()


class ReferenceImage(models.Model):
    class Kind(models.TextChoices):
        REF = 'ref', 'Референс'
        POSE = 'pose', 'Поза'
        COLOR = 'color', 'Цвет/палитра'
        MOOD = 'mood', 'Мудборд'
        OTHER = 'other', 'Другое'

    commission = models.ForeignKey(
        'artworks.Commission',
        on_delete=models.CASCADE,
        related_name='references',
    )
    image = models.ImageField(
        upload_to='refs/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
    )

    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.REF)
    caption = models.CharField(max_length=255, blank=True)
    source_url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)

    uploaded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Ref #{self.id} for commission {self.commission_id}"


def one_year_from_now():
    return timezone.now().date().replace(year=timezone.now().year + 1)


class Artwork(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    TYPE_CHOICES = [
        ('lineart', 'Лайнарт'),
        ('flat_colors', 'Плоские цвета'),
        ('sketch', 'Скетч'),
        ('basic_render', 'Базовый рендер'),
        ('premium_render', 'Премиальный рендер'),
    ]

    PURPOSE_CHOICES = [
        ('commission', 'Заказ'),
        ('promo', 'Промоматериалы'),
        ('collab', 'Коллаборация'),
    ]

    final_image = models.ImageField(
        upload_to='artworks/finals/%Y/%m/',
        null=True, blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
    )

    description = models.TextField()
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    purpose = models.CharField(max_length=50, choices=PURPOSE_CHOICES, default='commission')
    slot = models.ForeignKey(Slot, null=True, blank=True, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    commission = models.ForeignKey('artworks.Commission', null=True, blank=True, on_delete=models.CASCADE)

    expected_completion_date = models.DateField(null=True, blank=True)
    actual_completion_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Artwork by {self.client.name} with {self.artist.name}"


class Commission(models.Model):
    name = models.CharField("Название", max_length=200, null=True, blank=True)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="commissions")
    commissioner = models.ForeignKey(
        Commissioner,
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        related_name="commissions",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=currency_choices, default='USD')
    accepted_at = models.DateField(auto_now_add=True)
    description = models.TextField(max_length=1500, blank=True)

    def __str__(self):
        return self.name or f"Комиссия #{self.pk or '—'}"


class PriceEntry(models.Model):
    artist = models.ForeignKey(Artist, related_name='pricelist', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True)
    image = models.ImageField(upload_to='pricelist/', null=True, blank=True,
                              validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])])

    def __str__(self):
        if self.title:
            return self.title
        elif self.image:
            return f'Изображение для {self.artist.name}'
        return f'Пустая запись ({self.artist.name})'
