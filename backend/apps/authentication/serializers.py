"""
Serializers for authentication app.
"""
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from apps.authentication.models import User, OTP, UserSession
from apps.core.financial_access import user_may_login
from apps.core.utils import generate_otp, validate_phone, validate_mpin
from apps.core.exceptions import InvalidCredentials, InvalidMPIN, InvalidOTP
from apps.authentication.services import get_valid_otp
from django.conf import settings


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    phone = serializers.CharField(max_length=10)
    password = serializers.CharField(write_only=True)
    
    def validate_phone(self, value):
        """Validate phone number."""
        if not validate_phone(value):
            raise serializers.ValidationError("Invalid phone number format.")
        return value
    
    def validate(self, attrs):
        """Validate credentials."""
        phone = attrs.get('phone')
        password = attrs.get('password')
        
        if not phone or not password:
            raise serializers.ValidationError("Phone and password are required.")
        
        user = User.objects.filter(phone=phone).first()
        if not user or not user.check_password(password):
            raise InvalidCredentials("Invalid phone number or password.")

        if not user_may_login(user):
            raise serializers.ValidationError("User account is disabled.")

        attrs['user'] = user
        return attrs


class MPINVerificationSerializer(serializers.Serializer):
    """Serializer for MPIN verification."""
    mpin = serializers.CharField(max_length=6)
    
    def validate_mpin(self, value):
        """Validate MPIN format."""
        if not validate_mpin(value):
            raise serializers.ValidationError("MPIN must be 6 digits.")
        return value
    
    def validate(self, attrs):
        """Verify MPIN."""
        user = self.context['request'].user
        mpin = attrs.get('mpin')

        if not user_may_login(user):
            raise serializers.ValidationError('This account has been disabled. Contact support.')

        if not user.check_mpin(mpin):
            raise InvalidMPIN("Invalid MPIN.")

        return attrs


class SendOTPSerializer(serializers.Serializer):
    """Serializer for sending OTP."""
    CHANNEL_CHOICES = [('sms', 'SMS'), ('email', 'Email')]

    phone = serializers.CharField(max_length=10)
    purpose = serializers.ChoiceField(choices=OTP.PURPOSE_CHOICES, default='password-reset')
    channel = serializers.ChoiceField(choices=CHANNEL_CHOICES, default='sms', required=False)

    def validate_phone(self, value):
        """Validate phone number."""
        if not validate_phone(value):
            raise serializers.ValidationError("Invalid phone number format.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        purpose = attrs.get('purpose', 'password-reset')
        channel = (attrs.get('channel') or 'sms').strip().lower()
        from apps.authentication.constants import AUTH_OTP_EMAIL_PURPOSES

        if channel == 'email' and purpose not in AUTH_OTP_EMAIL_PURPOSES:
            raise serializers.ValidationError(
                {'channel': 'Email delivery is only supported for password reset and MPIN reset.'}
            )
        attrs['channel'] = channel
        return attrs


class VerifyOTPSerializer(serializers.Serializer):
    """Serializer for OTP verification."""
    phone = serializers.CharField(max_length=10)
    code = serializers.CharField(max_length=6)
    purpose = serializers.ChoiceField(choices=OTP.PURPOSE_CHOICES, default='password-reset')
    
    def validate_phone(self, value):
        """Validate phone number."""
        if not validate_phone(value):
            raise serializers.ValidationError("Invalid phone number format.")
        return value
    
    def validate(self, attrs):
        """Verify OTP (does not consume — reset step marks it used)."""
        phone = attrs.get('phone')
        code = attrs.get('code')
        purpose = attrs.get('purpose')
        attrs['otp_record'] = get_valid_otp(phone, code, purpose)
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for password reset."""
    phone = serializers.CharField(max_length=10)
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    
    def validate_phone(self, value):
        """Validate phone number."""
        if not validate_phone(value):
            raise serializers.ValidationError("Invalid phone number format.")
        return value
    
    def validate(self, attrs):
        """Validate password reset data."""
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError("Passwords do not match.")
        
        phone = attrs.get('phone')
        otp_code = attrs.get('otp')
        attrs['otp_record'] = get_valid_otp(phone, otp_code, 'password-reset')
        return attrs


class ResetMPINSerializer(serializers.Serializer):
    """Serializer for MPIN reset after OTP verification."""
    phone = serializers.CharField(max_length=10)
    otp = serializers.CharField(max_length=6)
    new_mpin = serializers.CharField(write_only=True, min_length=6, max_length=6)
    confirm_mpin = serializers.CharField(write_only=True, min_length=6, max_length=6)

    def validate_phone(self, value):
        if not validate_phone(value):
            raise serializers.ValidationError("Invalid phone number format.")
        return value

    def validate_new_mpin(self, value):
        if not validate_mpin(value):
            raise serializers.ValidationError("MPIN must be 6 digits.")
        return value

    def validate(self, attrs):
        new_mpin = attrs.get('new_mpin')
        confirm_mpin = attrs.get('confirm_mpin')
        if new_mpin != confirm_mpin:
            raise serializers.ValidationError("MPINs do not match.")

        phone = attrs.get('phone')
        otp_code = attrs.get('otp')
        attrs['otp_record'] = get_valid_otp(phone, otp_code, 'mpin-reset')
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model (login /me). Includes onboarding gate for hierarchy-created users."""

    onboarding = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'user_id', 'phone', 'email', 'first_name', 'last_name',
            'role', 'is_active', 'is_restricted', 'payments_locked',
            'pay_in_allowed_when_disabled', 'created_at', 'onboarding',
        ]
        read_only_fields = [
            'id', 'user_id', 'created_at', 'is_restricted', 'payments_locked',
            'pay_in_allowed_when_disabled',
        ]

    def get_onboarding(self, obj):
        from apps.users.models import KYC

        kyc = KYC.objects.filter(user=obj).first()
        pan_ok = bool(kyc and kyc.pan_verified)
        ad_ok = bool(kyc and kyc.aadhaar_verified)
        kyc_complete = bool(
            kyc
            and (
                kyc.verification_status == 'verified'
                or (pan_ok and ad_ok)
            )
        )
        has_mpin = bool(obj.mpin_hash)
        return {
            'kyc_status': kyc.verification_status if kyc else 'pending',
            'kyc_complete': kyc_complete,
            'pan_verified': pan_ok,
            'aadhaar_verified': ad_ok,
            'mpin_set': has_mpin,
            'account_ready': kyc_complete and has_mpin,
            'must_change_password': bool(getattr(obj, 'must_change_password', False)),
        }


class ForcedPasswordResetSendOTPSerializer(serializers.Serializer):
    """Authenticated first-login OTP channel selection."""
    channel = serializers.ChoiceField(choices=['sms', 'email'], default='sms')


class ForcedPasswordResetCompleteSerializer(serializers.Serializer):
    """Authenticated first-login password reset after OTP."""
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        if new_password != confirm_password:
            raise serializers.ValidationError('Passwords do not match.')
        return attrs


class OnboardingPANSerializer(serializers.Serializer):
    pan = serializers.CharField(max_length=10)


class OnboardingAadhaarSerializer(serializers.Serializer):
    aadhaar = serializers.CharField(max_length=12)


class OnboardingAadhaarVerifyOTPSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6)


class SetupMPINSerializer(serializers.Serializer):
    """First-time MPIN after KYC."""

    mpin = serializers.CharField(max_length=6, min_length=6)
    confirm_mpin = serializers.CharField(max_length=6, min_length=6)

    def validate_mpin(self, value):
        if not validate_mpin(value):
            raise serializers.ValidationError('MPIN must be 6 digits.')
        return value

    def validate(self, attrs):
        if attrs.get('mpin') != attrs.get('confirm_mpin'):
            raise serializers.ValidationError({'confirm_mpin': 'MPIN and confirmation do not match.'})
        return attrs
