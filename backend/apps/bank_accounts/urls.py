"""
URL configuration for bank_accounts app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.bank_accounts import views

router = DefaultRouter()
router.register(r'', views.BankAccountViewSet, basename='bank-account')

app_name = 'bank_accounts'

urlpatterns = [
    path('', include(router.urls)),
]
