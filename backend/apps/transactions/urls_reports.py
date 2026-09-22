"""
URL configuration for reports endpoints.
"""
from django.urls import path
from apps.transactions import views
from apps.transactions import report_revenue

app_name = 'reports'

urlpatterns = [
    path(
        'dashboard/transaction-status-counts/',
        views.dashboard_transaction_status_counts_view,
        name='dashboard-transaction-status-counts',
    ),
    path(
        'dashboard/recent/',
        views.dashboard_recent_transactions_view,
        name='dashboard-recent-transactions',
    ),
    path(
        'dashboard/summary/',
        views.dashboard_todays_summary_view,
        name='dashboard-todays-summary',
    ),
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
    # Unified revenue report (commission + service fees)
    path('revenue/', report_revenue.revenue_report_view, name='revenue-report'),
    path('revenue/summary/', report_revenue.revenue_summary_view, name='revenue-summary'),
    path(
        'revenue/breakdown/<str:service_id>/',
        report_revenue.revenue_breakdown_view,
        name='revenue-breakdown',
    ),
    path('revenue/export.csv', report_revenue.revenue_export_csv, name='revenue-export'),
    path(
        'revenue/unattributed/',
        report_revenue.unattributed_revenue_view,
        name='revenue-unattributed',
    ),
]
