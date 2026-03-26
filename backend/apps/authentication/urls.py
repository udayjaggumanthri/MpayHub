"""
URL configuration for authentication app.
"""
from django.urls import path
from apps.authentication import views

app_name = 'authentication'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('verify-mpin/', views.verify_mpin_view, name='verify-mpin'),
    path('send-otp/', views.send_otp_view, name='send-otp'),
    path('verify-otp/', views.verify_otp_view, name='verify-otp'),
    path('reset-password/', views.reset_password_view, name='reset-password'),
    path('refresh-token/', views.refresh_token_view, name='refresh-token'),
    path('logout/', views.logout_view, name='logout'),
    path('me/', views.current_user_view, name='current-user'),
]
