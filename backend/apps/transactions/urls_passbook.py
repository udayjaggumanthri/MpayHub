"""
URL configuration for passbook endpoints.
"""
from django.urls import path
from apps.transactions import views

app_name = 'passbook'

urlpatterns = [
    path('', views.passbook_view, name='passbook'),
]
