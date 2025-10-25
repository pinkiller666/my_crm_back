from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import URLValidator
from common.choices import SocialMediaChoices
from django.utils import timezone


class User(AbstractUser):
    ROLE_CHOICES = [
        ('artist', '🎨 Artist'),
        ('manager', '📋 Manager'),
        ('middleman', '💸 Middleman'),
        ('client', '🧍 Client'),
        ('admin', '🛠 Admin'),
    ]

    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='client')
    name = models.CharField(max_length=50)

    def __str__(self):
        roles = []
        if hasattr(self, 'as_artist'):
            roles.append('🎨 artist')
        if hasattr(self, 'as_manager'):
            roles.append('📋 manager')
        if hasattr(self, 'as_middleman'):
            roles.append('💸 middleman')
        if self.is_superuser:
            roles.append('👑 admin')

        role_display = ', '.join(roles) if roles else '👤 user'
        return f"{self.name or self.username} ({role_display})"


class Middleman(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='middleman_profile')
    percent = models.DecimalField(max_digits=5, decimal_places=2)
    paypal_address = models.CharField(max_length=70)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.percent}%)"


class Manager(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='as_manager', null=True, blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Artist(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='as_artist',
        null=False, blank=False
    )

    manager = models.ForeignKey(
        "identity.Manager",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="artists",
        verbose_name="Менеджер"
    )

    class Meta:
        ordering = ("user__username",)  # или ("id",)

    def __str__(self):
        return (
                getattr(self, "full_name", None)
                or getattr(self, "display_name", None)
                or (self.user.get_full_name() if self.user else None)
                or (self.user.username if self.user else None)
                or f"Artist #{self.pk}"
        )


class ArtistContact(models.Model):
    artist = models.ForeignKey(
        "identity.Artist",
        on_delete=models.CASCADE,
        related_name="contacts",
        verbose_name="Художник",
    )
    social_media = models.CharField(
        max_length=50,
        choices=SocialMediaChoices,
        verbose_name="Соцсеть",
    )
    handle = models.CharField(
        max_length=255,
        verbose_name="Адрес/идентификатор",
        help_text="Ник, @handle, email или иное представление"
    )
    url = models.URLField(
        blank=True,
        validators=[URLValidator()],
        verbose_name="Ссылка"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Заметки"
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Контакт художника"
        verbose_name_plural = "Контакты художника"
        constraints = [
            # уникальность в рамках одного художника по соцсети+handle
            models.UniqueConstraint(
                fields=["artist", "social_media", "handle"],
                name="uniq_artist_contact"
            )
        ]
        indexes = [
            models.Index(fields=["artist", "social_media"]),
        ]

    def __str__(self):
        return f"{self.get_social_media_display()}: {self.handle}"


class Commissioner(models.Model):
    name = models.CharField(max_length=255)
    paypal_email = models.EmailField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CommissionerContact(models.Model):
    """
    Универсальная «точка контакта»: соцсети, мессенджеры, сайт, никнеймы.
    Примеры:
      kind=twitter,   handle=@tomchlenozavr, url=https://twitter.com/tomchlenozavr
      kind=telegram,  handle=@totallynormaltom, url=https://t.me/totallynormaltom
      kind=website,   handle=portfolio, url=https://tom.art
    """

    commissioner = models.ForeignKey(
        Commissioner, on_delete=models.CASCADE, related_name="contacts"
    )
    social_media = models.CharField(
        max_length=50,
        choices=SocialMediaChoices,
        verbose_name="Соцсеть",
    )
    handle = models.CharField(
        max_length=255,
        help_text="Ник/идентификатор, можно с @"
    )
    url = models.URLField(max_length=500, blank=True, validators=[URLValidator()])

    class Meta:
        verbose_name = "Контакт/соцсеть"
        verbose_name_plural = "Контакты/соцсети"
        constraints = [
            # чтобы не плодить дубликаты в рамках одного комиссионера
            models.UniqueConstraint(
                fields=["commissioner", "social_media", "handle"],
                name="uniq_comm_contact"
            )
        ]
        indexes = [models.Index(fields=["commissioner", "social_media"])]

    def __str__(self):
        return f"{self.get_social_media_display()}: {self.handle}"
