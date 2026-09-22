"""
URL configuration for wallets app.
"""
from django.urls import path
from apps.wallets import views

app_name = 'wallets'

urlpatterns = [
    path('', views.get_wallets_view, name='wallets'),
    path('transfer-to-bbps/', views.transfer_main_to_bbps_view, name='transfer-to-bbps'),
    # Distributed Balance drill-down (must be before <wallet_type> catch-alls).
    path('distributed/ledger/', views.distributed_ledger_view, name='distributed-ledger'),
    path(
        'distributed/network/<int:user_id>/',
        views.distributed_network_view,
        name='distributed-network',
    ),
    path('<str:wallet_type>/', views.get_wallet_view, name='wallet'),
    path('<str:wallet_type>/history/', views.get_wallet_history_view, name='wallet-history'),
]
