"""URL configuration for core app (system-wide endpoints)."""
from django.urls import path

from apps.core import views

app_name = 'core'

urlpatterns = [
    path('maintenance-status/', views.maintenance_status_view, name='maintenance-status'),
    path('appearance/', views.appearance_status_view, name='appearance-status'),
]
