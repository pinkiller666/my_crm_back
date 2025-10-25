from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Account

User = get_user_model()

@receiver(post_save, sender=User)
def create_default_account(sender, instance, created, **kwargs):
    if created:
        # Если у пользователя нет счетов — создаём дефолтный primary
        if not Account.objects.filter(user=instance).exists():
            Account.objects.create(
                user=instance,
                name="Основной счет",
                is_primary=True,
            )