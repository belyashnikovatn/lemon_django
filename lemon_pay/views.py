from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from rest_framework import generics
from .serializers import UserSerializer, SubscriptionSerializer
from .permissions import HasActiveSubscription
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import requests
import hmac
import hashlib
from django.http import HttpResponse
import json
from .models import Subscription
from django.shortcuts import render
from django.utils import timezone
from urllib.parse import urlparse, parse_qs


User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """
    Регистрация пользователя
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer


class LoginView(TokenObtainPairView):
    """
    Логин пользователя
    """

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            user = User.objects.get(username=request.data["username"])
            response.data["user"] = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            }
        return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout(request):
    """
    Создание checkout в Lemon Squeezy
    """
    headers = {
        "Authorization": f"Bearer {settings.LEMON_API_KEY}",
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
    }

    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_data": {
                    "email": request.user.email,
                    "name": request.user.username,
                    "custom": {"user_id": str(request.user.id)},
                },
                "product_options": {
                    "redirect_url": f"{settings.SITE_DOMAIN}/success/{{checkout_id}}/",
                },
            },
            "relationships": {
                "store": {
                    "data": {
                        "type": "stores",
                        "id": str(settings.LEMON_STORE_ID),
                    }
                },
                "variant": {
                    "data": {
                        "type": "variants",
                        "id": str(settings.LEMON_VARIANT_ID),
                    }
                },
            },
        }
    }

    try:
        res = requests.post(
            f"{settings.LEMON_BASE_URL}/checkouts",
            headers=headers,
            json=payload,
            timeout=10,  # Таймаут для запроса
        )

        # Если статус не 201 Created
        if res.status_code != 201:
            error_detail = (
                res.json()
                .get("errors", [{}])[0]
                .get("detail", "Unknown error")
            )
            return Response(
                {
                    "error": "Ошибка при создании checkout",
                    "status_code": res.status_code,
                    "detail": error_detail,
                    "lemon_response": res.json(),
                },
                status=400,
            )

        data = res.json()
        checkout_url = data.get("data", {}).get("attributes", {}).get("url")

        # Парсим URL для извлечения дополнительных данных
        parsed_url = urlparse(checkout_url)
        query_params = parse_qs(parsed_url.query)

        return Response(
            {
                "checkout_url": checkout_url,
                "checkout_id": parsed_url.path.split("/")[-1],
                "signature": query_params.get("signature", [""])[0],
            }
        )

    except requests.exceptions.RequestException as e:
        error_msg = f"Ошибка подключения к Lemon Squeezy: {str(e)}"
        return Response({"error": error_msg}, status=503)
    except Exception as e:
        error_msg = f"Неожиданная ошибка: {str(e)}"
        return Response({"error": error_msg}, status=500)


def verify_signature(request):
    """
    Проверка подписи вебхука
    """
    print("Headers:", request.headers)
    signature = request.headers.get("X-Signature")
    if not signature:
        print("No signature provided")
        return False
    secret = settings.LEMON_WEBHOOK_SECRET.encode()
    computed = hmac.new(secret, request.body, hashlib.sha256).hexdigest()
    is_valid = hmac.compare_digest(computed, signature)

    if not is_valid:
        print("Signature mismatch")
    return is_valid


@csrf_exempt
@api_view(["POST"])
@permission_classes([])  # публичный доступ
def lemon_webhook(request):
    """
    Обработка вебхука от Lemon Squeezy
    """
    if not verify_signature(request):
        return HttpResponse("Invalid signature", status=403)

    try:
        body = request.body.decode("utf-8")
        data = json.loads(body)
        print("Webhook data parsed:", data)
    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON", status=400)

    event = data.get("meta", {}).get("event_name")
    custom_data = data.get("meta", {}).get("custom_data", {})
    user_id = custom_data.get("user_id")
    subscription_id = data.get("data", {}).get("id")
    customer_id = data.get("data", {}).get("attributes", {}).get("customer_id")
    print(f"[Webhook] Event: {event}")
    print(f"[Webhook] Extracted user_id: {user_id}")
    print(f"[Webhook] subscription_id: {subscription_id}")
    print(f"[Webhook] customer_id: {customer_id}")

    if not user_id:
        return HttpResponse("User ID is missing", status=400)

    if event == "subscription_created":
        try:
            user = User.objects.get(id=user_id)
            Subscription.objects.update_or_create(
                user=user,
                defaults={
                    "lemon_subscription_id": subscription_id,
                    "lemon_customer_id": customer_id,
                    "is_active": True,
                },
            )
            print(f"Subscription created for user {user_id}")
        except User.DoesNotExist:
            print(f"User with ID {user_id} not found")
            return HttpResponse("User not found", status=404)
    elif event in ["subscription_cancelled", "subscription_expired"]:
        Subscription.objects.filter(
            lemon_subscription_id=subscription_id
        ).update(is_active=False)
        print(f"Subscription {subscription_id} cancelled or expired")
    elif event == "subscription_resumed":
        Subscription.objects.filter(
            lemon_subscription_id=subscription_id
        ).update(is_active=True)
        print(f"Subscription {subscription_id} resumed")
    return HttpResponse("OK", status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticated, HasActiveSubscription])
def premium_content(request):
    """
    Пример защищенного контента
    """
    return Response({"message": "Добро пожаловать в премиум-зону 🚀"})


def payment_success(request, checkout_id=None):
    """
    Обработка успешного платежа
    """
    checkout_id = request.GET.get("checkout_id")
    return render(
        request,
        "payments/success.html",
        {
            "checkout_id": checkout_id or "не указан",
            "message": "Спасибо за покупку! Ваша подписка успешно активирована.",
        },
    )


def payment_receipt(request, checkout_id):
    """
    Обработка квитанции
    """
    return render(
        request,
        "payments/receipt.html",  # Обновленный путь
        {
            "checkout_id": checkout_id,
            "email": (
                request.user.email
                if request.user.is_authenticated
                else "customer@example.com"
            ),
            "date": timezone.now().strftime("%d.%m.%Y %H:%M"),
            "amount": "9.99$",
        },
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def subscription_status(request):
    """
    Получение статуса подписки
    """
    user_id = request.user.id
    try:
        user = User.objects.get(id=user_id)
        sub = user.subscription
        return Response(
            {
                "is_active": sub.is_active,
                "subscription_id": sub.lemon_subscription_id,
            }
        )
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)
    except AttributeError:
        return Response({"is_active": False})
