"""
URL configuration for reports endpoints.
"""
from django.urls import path
from apps.transactions import views

app_name = 'reports'

urlpatterns = [
    path('payin/', views.payin_report_view, name='payin-report'),
    path('payout/', views.payout_report_view, name='payout-report'),
    path('bbps/', views.bbps_report_view, name='bbps-report'),
    path('commission/', views.commission_report_view, name='commission-report'),
]
