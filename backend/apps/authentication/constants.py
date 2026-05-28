"""
Auth OTP purposes and email event mapping (loose coupling to notification catalog).
"""

# Purposes that may use email delivery (SMS uses AUTH_OTP_PURPOSE_TO_EVENT in notifications.catalog).
AUTH_OTP_EMAIL_PURPOSES = frozenset({'password-reset', 'mpin-reset'})

AUTH_OTP_PURPOSE_TO_EMAIL_EVENT = {
    'password-reset': 'auth.otp.password_reset',
    'mpin-reset': 'auth.otp.mpin_reset',
}
