from django.contrib import admin
from django.urls import path
from lemon_pay.views import (
    RegisterView,
    LoginView,
    create_checkout,
    lemon_webhook,
    premium_content,
    payment_success,
    payment_receipt,
    subscription_status,
)


urlpatterns = [
    path("admin/", admin.site.urls),
    # Аутентификация
    path("api/register/", RegisterView.as_view(), name="register"),
    path("api/login/", LoginView.as_view(), name="login"),
    # Работа с подписками
    path("api/create_checkout/", create_checkout, name="create_checkout"),
    path(
        "api/subscription_status/",
        subscription_status,
        name="subscription_status",
    ),
    path("api/premium_content/", premium_content, name="premium_content"),
    # Вебхуки
    path("api/lemon_webhook/", lemon_webhook, name="lemon_webhook"),
    # Платежные страницы
    path("success/", payment_success, name="payment_success"),
    path(
        "success/<str:checkout_id>/",
        payment_success,
        name="payment_success_with_id",
    ),
    path(
        "receipt/<str:checkout_id>/",
        payment_receipt,
        name="payment_receipt",
    ),
]
