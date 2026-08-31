"""
URL configuration for admin_panel app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.admin_panel import views
from apps.fund_management import views_qr_admin

router = DefaultRouter()
router.register(r'announcements', views.AnnouncementViewSet, basename='announcement')
router.register(r'gateways', views.PaymentGatewayViewSet, basename='payment-gateway')
router.register(r'payout-gateways', views.PayoutGatewayViewSet, basename='payout-gateway')
router.register(r'pay-in-packages', views.PayInPackageViewSet, basename='pay-in-package')

router.register(r'pay-in-qr-accounts', views_qr_admin.PayInQrAccountViewSet, basename='pay-in-qr-account')

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
    path(
        'sms-templates/<str:event_key>/fetch-msg91/',
        views.sms_template_fetch_msg91_view,
        name='sms-template-fetch-msg91',
    ),
    path('sms-logs/', views.sms_delivery_logs_view, name='sms-logs'),
    path('email-templates/', views.email_templates_list_view, name='email-templates'),
    path('email-templates/<str:event_key>/', views.email_template_detail_view, name='email-template-detail'),
    path('email-templates/<str:event_key>/test/', views.email_template_test_view, name='email-template-test'),
    path('maintenance/', views.maintenance_config_view, name='maintenance-config'),
    path('appearance/', views.appearance_config_view, name='appearance-config'),
    path('pay-in/qr-operations/stats/', views_qr_admin.qr_operations_stats_view, name='qr-operations-stats'),
    path('pay-in/qr-operations/', views_qr_admin.qr_operations_list_view, name='qr-operations-list'),
    path('pay-in/qr-operations/export.csv', views_qr_admin.qr_operations_export_csv_view, name='qr-operations-export'),
    path('pay-in/qr-operations/export.xlsx', views_qr_admin.qr_operations_export_xlsx_view, name='qr-operations-export-xlsx'),
    path('pay-in/qr-operations/<int:pk>/', views_qr_admin.qr_operations_detail_view, name='qr-operations-detail'),
    path('pay-in/qr-operations/<int:pk>/approve/', views_qr_admin.qr_operations_approve_view, name='qr-operations-approve'),
    path('pay-in/qr-operations/<int:pk>/reject/', views_qr_admin.qr_operations_reject_view, name='qr-operations-reject'),
    path('pay-in/qr-operations/<int:pk>/release-utr/', views_qr_admin.qr_operations_release_utr_view, name='qr-operations-release-utr'),
]
