"""
URL configuration for fund management app.
"""
from django.urls import path
from apps.fund_management import views

app_name = 'fund_management'

urlpatterns = [
    path('load-money/', views.load_money_view, name='load-money'),
    path('load-money/list/', views.load_money_list_view, name='load-money-list'),
    path('payout/', views.payout_view, name='payout'),
    path('payout/list/', views.payout_list_view, name='payout-list'),
    path('gateways/', views.get_gateways_view, name='gateways'),
]
