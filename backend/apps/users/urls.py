"""
URL configuration for users app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.users import views

router = DefaultRouter()
router.register(r'', views.UserViewSet, basename='user')

app_name = 'users'

urlpatterns = [
    path('', include(router.urls)),
]
