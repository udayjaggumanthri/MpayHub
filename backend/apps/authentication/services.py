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
from apps.authentication.constants import AUTH_OTP_EMAIL_PURPOSES
from apps.integrations.email_service import EmailDeliveryError, send_auth_otp_email
from apps.notifications.catalog import AUTH_OTP_PURPOSE_TO_EVENT
from apps.notifications.services.dispatch import SmsNotificationService


class SmtpNotConfiguredError(Exception):
    """Raised when email OTP is requested but SMTP is not available."""


def normalize_otp_code(code):
    return str(code or '').strip()


def get_valid_otp(phone, code, purpose):
    """
    Find an unused, non-expired OTP matching the submitted code (not merely the latest row).
    """
    normalized = normalize_otp_code(code)
    if not normalized:
        raise InvalidOTP('Invalid OTP code.')

    candidates = OTP.objects.filter(
        phone=phone,
        purpose=purpose,
        is_used=False,
        code=normalized,
    ).order_by('-created_at')

    for otp in candidates:
        if otp.is_valid():
            return otp

    if candidates.exists():
        raise InvalidOTP('OTP has expired or already used.')
    raise InvalidOTP('Invalid OTP code.')


def consume_otp(otp):
    """Mark a validated OTP as used."""
    if otp.is_used:
        raise InvalidOTP('OTP not found or already used.')
    if not otp.is_valid():
        raise InvalidOTP('OTP has expired or already used.')
    otp.mark_as_used()
    return otp


def create_jwt_tokens(user):
    """Create JWT access and refresh tokens for user."""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


def send_otp(phone, purpose='password-reset', channel='sms'):
    """
    Generate and send OTP via SMS or registered email (password-reset / mpin-reset).
    """
    channel = (channel or 'sms').strip().lower()
    if channel not in ('sms', 'email'):
        channel = 'sms'
    if channel == 'email' and purpose not in AUTH_OTP_EMAIL_PURPOSES:
        channel = 'sms'

    # Supersede any prior unused OTPs so only the newest code is valid.
    OTP.objects.filter(phone=phone, purpose=purpose, is_used=False).update(is_used=True)

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
            send_auth_otp_email(
                purpose=purpose,
                to_email=registered_email,
                otp_code=otp_code,
            )
        except EmailDeliveryError as exc:
            raise SmtpNotConfiguredError(str(exc)) from exc
        return otp

    event_key = AUTH_OTP_PURPOSE_TO_EVENT.get(purpose)
    if event_key:
        try:
            display_name = 'Customer'
            user_id = None
            user = User.objects.filter(phone=phone).select_related('profile').first()
            if user:
                user_id = user.pk
                profile = getattr(user, 'profile', None)
                if profile is not None:
                    display_name = (
                        f'{profile.first_name or ""} {profile.last_name or ""}'.strip()
                        or display_name
                    )
                if display_name == 'Customer':
                    display_name = (
                        (user.get_full_name() or '').strip()
                        or (user.first_name or '').strip()
                        or display_name
                    )
            SmsNotificationService.dispatch(
                event_key,
                phone,
                {
                    'name': display_name,
                    'otp': otp_code,
                },
                user_id=user_id,
                idempotency_key=f'otp:{purpose}:{phone}:{otp.pk}',
            )
        except Exception as e:
            print(f'Failed to send SMS: {e}')
            if settings.DEBUG:
                print(f'OTP for {phone}: {otp_code}')
    elif settings.DEBUG:
        print(f'OTP for {phone}: {otp_code} (no SMS event for purpose={purpose})')

    return otp


def verify_otp(phone, code, purpose='password-reset', *, consume=True):
    """
    Verify OTP code. When consume=True (default), marks the OTP as used.
    """
    otp = get_valid_otp(phone, code, purpose)
    if consume:
        consume_otp(otp)
    return otp


def reset_password(phone, otp_code, new_password, *, otp_record=None):
    """
    Reset user password after OTP verification.
    """
    otp = otp_record or get_valid_otp(phone, otp_code, 'password-reset')
    if normalize_otp_code(otp.code) != normalize_otp_code(otp_code):
        raise InvalidOTP('Invalid OTP code.')
    consume_otp(otp)

    try:
        user = User.objects.get(phone=phone)
    except User.DoesNotExist:
        raise InvalidCredentials("User not found.")

    user.set_password(new_password)
    user.save(update_fields=['password'])

    return user


def reset_mpin(phone, otp_code, new_mpin, *, otp_record=None):
    """
    Reset user MPIN after OTP verification (forgot MPIN flow).
    """
    otp = otp_record or get_valid_otp(phone, otp_code, 'mpin-reset')
    if normalize_otp_code(otp.code) != normalize_otp_code(otp_code):
        raise InvalidOTP('Invalid OTP code.')
    consume_otp(otp)

    try:
        user = User.objects.get(phone=phone)
    except User.DoesNotExist:
        raise InvalidCredentials("User not found.")

    if not user.mpin_hash:
        raise InvalidCredentials(
            "MPIN is not set on this account. Complete onboarding or contact support."
        )

    user.set_mpin(new_mpin)
    user.save(update_fields=['mpin_hash', 'updated_at'])

    return user
