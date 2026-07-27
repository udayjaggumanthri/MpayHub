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
    path('reset-mpin/', views.reset_mpin_view, name='reset-mpin'),
    path('refresh-token/', views.refresh_token_view, name='refresh-token'),
    path('logout/', views.logout_view, name='logout'),
    path('session-policy/', views.session_policy_view, name='session-policy'),
    path('my-activity/export/', views.my_activity_export_view, name='my-activity-export'),
    path('my-activity/', views.my_activity_view, name='my-activity'),
    path('me/', views.current_user_view, name='current-user'),
    path('me/profile-sync/pending/', views.profile_sync_pending_view, name='profile-sync-pending'),
    path('profile-sync/confirm/', views.profile_sync_confirm_view, name='profile-sync-confirm'),
    path('profile-sync/decline/', views.profile_sync_decline_view, name='profile-sync-decline'),
    path(
        'me/send-password-reset-otp/',
        views.send_forced_password_reset_otp_view,
        name='send-forced-password-reset-otp',
    ),
    path(
        'me/complete-password-reset/',
        views.complete_forced_password_reset_view,
        name='complete-forced-password-reset',
    ),
    path('change-password/', views.change_password_view, name='change-password'),
    path('change-mpin/', views.change_mpin_view, name='change-mpin'),
    path('onboarding/kyc/pan/', views.onboarding_kyc_verify_pan_view, name='onboarding-kyc-pan'),
    path(
        'onboarding/kyc/digilocker/init/',
        views.onboarding_kyc_digilocker_init_view,
        name='onboarding-kyc-digilocker-init',
    ),
    path(
        'onboarding/kyc/digilocker/status/',
        views.onboarding_kyc_digilocker_status_view,
        name='onboarding-kyc-digilocker-status',
    ),
    path(
        'onboarding/kyc/digilocker/complete/',
        views.onboarding_kyc_digilocker_complete_view,
        name='onboarding-kyc-digilocker-complete',
    ),
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
