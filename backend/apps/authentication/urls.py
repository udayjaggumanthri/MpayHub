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
    path('onboarding/kyc/pan/', views.onboarding_kyc_verify_pan_view, name='onboarding-kyc-pan'),
    path(
        'onboarding/kyc/aadhaar/send-otp/',
        views.onboarding_kyc_aadhaar_send_otp_view,
        name='onboarding-kyc-aadhaar-send-otp',
    ),
    path(
        'onboarding/kyc/aadhaar/verify-otp/',
        views.onboarding_kyc_aadhaar_verify_otp_view,
        name='onboarding-kyc-aadhaar-verify-otp',
    ),
    path('onboarding/setup-mpin/', views.setup_mpin_view, name='onboarding-setup-mpin'),
]
