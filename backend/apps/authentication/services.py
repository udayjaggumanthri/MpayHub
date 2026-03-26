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


def create_jwt_tokens(user):
    """Create JWT access and refresh tokens for user."""
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


def send_otp(phone, purpose='password-reset'):
    """
    Generate and send OTP to user's phone.
    """
    # Generate OTP
    otp_code = generate_otp(settings.OTP_LENGTH)
    
    # Calculate expiry time
    expires_at = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    
    # Create OTP record
    otp = OTP.objects.create(
        phone=phone,
        code=otp_code,
        purpose=purpose,
        expires_at=expires_at
    )
    
    # Send OTP via SMS (with fallback to console in development)
    try:
        sms_service = SMSService()
        sms_service.send_otp(phone, otp_code, purpose)
    except Exception as e:
        # Log error but don't fail - OTP is still created
        print(f"Failed to send SMS: {e}")
        # In development, print OTP to console
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
        
        # Mark OTP as used
        otp.mark_as_used()
        
        return otp
    except OTP.DoesNotExist:
        raise InvalidOTP("OTP not found or already used.")


def reset_password(phone, otp_code, new_password):
    """
    Reset user password after OTP verification.
    """
    # Verify OTP first
    verify_otp(phone, otp_code, purpose='password-reset')
    
    # Get user
    try:
        user = User.objects.get(phone=phone)
    except User.DoesNotExist:
        raise InvalidCredentials("User not found.")
    
    # Set new password
    user.set_password(new_password)
    user.save(update_fields=['password'])
    
    return user
