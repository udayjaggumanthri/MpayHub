"""
URL configuration for transactions app.
"""
from django.urls import path
from apps.transactions import views

app_name = 'transactions'

urlpatterns = [
    # Transactions endpoints
    path('', views.transactions_list_view, name='transactions'),
    path('<int:transaction_id>/', views.transaction_detail_view, name='transaction-detail'),
    # Passbook endpoint (accessed via /api/passbook/)
    path('', views.passbook_view, name='passbook'),
    # Reports endpoints (accessed via /api/reports/)
    path('payin/', views.payin_report_view, name='payin-report'),
    path('payout/', views.payout_report_view, name='payout-report'),
    path('bbps/', views.bbps_report_view, name='bbps-report'),
    path('commission/', views.commission_report_view, name='commission-report'),
]
