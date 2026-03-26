"""
URL configuration for contacts app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.contacts import views

router = DefaultRouter()
router.register(r'', views.ContactViewSet, basename='contact')

app_name = 'contacts'

urlpatterns = [
    path('', include(router.urls)),
]
