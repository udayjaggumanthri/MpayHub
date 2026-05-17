"""
Authentication business logic services.
"""
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from apps.authentication.models import User, OTP, UserSession
from apps.core.utils import generate_otp
from apps.core.exceptions import InvalidCredentials, InvalidOTP
from apps.integrations.sms_service import SMSService
from apps.integrations.email_service import EmailDeliveryError, send_password_reset_otp_email


class SmtpNotConfiguredError(Exception):
    """Raised when email OTP is requested but SMTP is not available."""


def create_jwt_tokens(user):
    """Create JWT access and refresh tokens for user."""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


def send_otp(phone, purpose='password-reset', channel='sms'):
    """
    Generate and send OTP to user's phone (SMS) or registered email (password-reset only).
    """
    channel = (channel or 'sms').strip().lower()
    if channel not in ('sms', 'email'):
        channel = 'sms'
    if channel == 'email' and purpose != 'password-reset':
        channel = 'sms'

    otp_code = generate_otp(settings.OTP_LENGTH)
    expires_at = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

    otp = OTP.objects.create(
        phone=phone,
        code=otp_code,
        purpose=purpose,
        expires_at=expires_at,
        delivery_channel=channel,
    )

    if channel == 'email':
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            raise InvalidCredentials("User not found.")
        registered_email = (user.email or '').strip()
        if not registered_email:
            raise SmtpNotConfiguredError(
                'No registered email on this account. Use SMS or contact support.'
            )
        try:
            send_password_reset_otp_email(to_email=registered_email, otp_code=otp_code)
        except EmailDeliveryError as exc:
            raise SmtpNotConfiguredError(str(exc)) from exc
        return otp

    try:
        sms_service = SMSService()
        sms_service.send_otp(phone, otp_code, purpose)
    except Exception as e:
        print(f"Failed to send SMS: {e}")
        if settings.DEBUG:
            print(f"OTP for {phone}: {otp_code}")

    return otp


def verify_otp(phone, code, purpose='password-reset'):
    """
    Verify OTP code.
    Returns the OTP object if valid, raises exception otherwise.
    """
    try:
        otp = OTP.objects.filter(
            phone=phone,
            purpose=purpose,
            is_used=False
        ).latest('created_at')

        if not otp.is_valid():
            raise InvalidOTP("OTP has expired or already used.")

        if otp.code != code:
            raise InvalidOTP("Invalid OTP code.")

        otp.mark_as_used()

        return otp
    except OTP.DoesNotExist:
        raise InvalidOTP("OTP not found or already used.")


def reset_password(phone, otp_code, new_password):
    """
    Reset user password after OTP verification.
    """
    verify_otp(phone, otp_code, purpose='password-reset')

    try:
        user = User.objects.get(phone=phone)
    except User.DoesNotExist:
        raise InvalidCredentials("User not found.")

    user.set_password(new_password)
    user.save(update_fields=['password'])

    return user
