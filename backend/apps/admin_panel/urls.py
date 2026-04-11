"""
URL configuration for admin_panel app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.admin_panel import views

router = DefaultRouter()
router.register(r'announcements', views.AnnouncementViewSet, basename='announcement')
router.register(r'gateways', views.PaymentGatewayViewSet, basename='payment-gateway')
router.register(r'payout-gateways', views.PayoutGatewayViewSet, basename='payout-gateway')
router.register(r'pay-in-packages', views.PayInPackageViewSet, basename='pay-in-package')

app_name = 'admin_panel'

urlpatterns = [
    path('', include(router.urls)),
]
