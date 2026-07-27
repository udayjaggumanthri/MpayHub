"""URL configuration for session security admin APIs."""
from django.urls import path

from apps.session_security import views

app_name = 'session_security'

urlpatterns = [
    path('settings/', views.settings_view, name='settings'),
    path('audit-logs/export/', views.audit_logs_export_view, name='audit-logs-export'),
    path('audit-logs/', views.audit_logs_view, name='audit-logs'),
    path('concurrent-exceptions/', views.concurrent_exceptions_view, name='concurrent-exceptions'),
    path('users/search/', views.search_users_for_exception_view, name='users-search'),
    path('sessions/<int:session_id>/terminate/', views.terminate_session_view, name='terminate-session'),
    path('idle-policy/', views.public_idle_policy_view, name='idle-policy'),
]
