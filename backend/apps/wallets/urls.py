"""
URL configuration for wallets app.
"""
from django.urls import path
from apps.wallets import views

app_name = 'wallets'

urlpatterns = [
    path('', views.get_wallets_view, name='wallets'),
    path('<str:wallet_type>/', views.get_wallet_view, name='wallet'),
    path('<str:wallet_type>/history/', views.get_wallet_history_view, name='wallet-history'),
]
