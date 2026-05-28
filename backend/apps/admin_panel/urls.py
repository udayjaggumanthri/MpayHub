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
    path('payout-slab-config/', views.payout_slab_config_view, name='payout-slab-config'),
    path('smtp-config/', views.smtp_config_list_view, name='smtp-config'),
    path('smtp-config/<int:pk>/', views.smtp_config_detail_view, name='smtp-config-detail'),
    path('smtp-config/<int:pk>/activate/', views.smtp_config_activate_view, name='smtp-config-activate'),
    path('smtp-config/<int:pk>/deactivate/', views.smtp_config_deactivate_view, name='smtp-config-deactivate'),
    path('smtp-config/<int:pk>/secrets/', views.smtp_config_secrets_view, name='smtp-config-secrets'),
    path('smtp-config/<int:pk>/test/', views.smtp_config_test_view, name='smtp-config-test'),
    path('sms-config/', views.sms_config_list_view, name='sms-config'),
    path('sms-config/<int:pk>/', views.sms_config_detail_view, name='sms-config-detail'),
    path('sms-config/<int:pk>/activate/', views.sms_config_activate_view, name='sms-config-activate'),
    path('sms-config/<int:pk>/deactivate/', views.sms_config_deactivate_view, name='sms-config-deactivate'),
    path('sms-config/<int:pk>/secrets/', views.sms_config_secrets_view, name='sms-config-secrets'),
    path('sms-config/<int:pk>/test/', views.sms_config_test_view, name='sms-config-test'),
    path('sms-templates/', views.sms_templates_list_view, name='sms-templates'),
    path('sms-templates/<str:event_key>/', views.sms_template_update_view, name='sms-template-update'),
    path('sms-templates/<str:event_key>/test/', views.sms_template_test_view, name='sms-template-test'),
    path('email-templates/', views.email_templates_list_view, name='email-templates'),
    path('email-templates/<str:event_key>/', views.email_template_detail_view, name='email-template-detail'),
    path('email-templates/<str:event_key>/test/', views.email_template_test_view, name='email-template-test'),
]
