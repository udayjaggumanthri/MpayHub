"""Integration webhooks (Razorpay, PayU, ...)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.integrations import views

app_name = 'integrations'

router = DefaultRouter()
router.register(r'api-masters', views.ApiMasterViewSet, basename='api-master')

urlpatterns = [
    path('', include(router.urls)),
    path('razorpay/webhook/', views.RazorpayWebhookView.as_view(), name='razorpay-webhook'),
    path('payu/webhook/', views.PayUWebhookView.as_view(), name='payu-webhook'),
    path(
        'cashfree/digilocker/webhook/',
        views.CashfreeDigilockerWebhookView.as_view(),
        name='cashfree-digilocker-webhook',
    ),
    path(
        'payout/vimopay/callback/',
        views.PayoutProviderCallbackView.as_view(),
        {'provider_code': 'vimopay'},
        name='vimopay-payout-callback',
    ),
    path(
        'payout/<str:provider_code>/callback/',
        views.PayoutProviderCallbackView.as_view(),
        name='payout-provider-callback',
    ),
]
