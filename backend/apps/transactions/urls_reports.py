"""
URL configuration for reports endpoints.
"""
from django.urls import path
from apps.transactions import views

app_name = 'reports'

urlpatterns = [
    path('analytics/summary/', views.analytics_summary_view, name='analytics-summary'),
    path('payin/', views.payin_report_view, name='payin-report'),
    path('payin/export.csv', views.payin_report_export_csv, name='payin-report-export'),
    path('payout/', views.payout_report_view, name='payout-report'),
    path('payout/export.csv', views.payout_report_export_csv, name='payout-report-export'),
    path('bbps/', views.bbps_report_view, name='bbps-report'),
    path('bbps/export.csv', views.bbps_report_export_csv, name='bbps-report-export'),
    path('passbook/export.csv', views.passbook_report_export_csv, name='passbook-report-export'),
    path('commission/', views.commission_report_view, name='commission-report'),
    path('commission/export.csv', views.commission_report_export_csv, name='commission-report-export'),
]
