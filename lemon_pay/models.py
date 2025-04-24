from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Расширение абстрактного юзера"""

    def __str__(self):
        return f"name: {self.username}"


class Subscription(models.Model):
    """Подписка пользователя: 1-1"""
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='subscription')
    lemon_subscription_id = models.CharField(max_length=255, unique=True)
    lemon_customer_id = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
