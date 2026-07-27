"""
Serializers for authentication app.
"""
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from apps.authentication.models import User, OTP, UserSession
from apps.core.access_catalog import ACCESS_CODE_USER_DISABLED, user_message_for_code
from apps.core.financial_access import user_may_login
from apps.core.utils import generate_otp, validate_phone, validate_mpin
from apps.core.exceptions import InvalidCredentials, InvalidMPIN, InvalidOTP
from apps.authentication.services import get_valid_otp
from django.conf import settings


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    phone = serializers.CharField(max_length=10)
    password = serializers.CharField(write_only=True)
    client_context = serializers.JSONField(required=False, allow_null=True)

    def validate_phone(self, value):
        """Validate phone number."""
        if not validate_phone(value):
            raise serializers.ValidationError("Invalid phone number format.")
        return value

    def validate_client_context(self, value):
        """Optional bag — size-bound; deep sanitize happens in session_security."""
        if value is None:
            return None
        if not isinstance(value, dict):
            raise serializers.ValidationError('client_context must be an object.')
        # Soft size guard to avoid oversized payloads
        import json

        try:
            raw = json.dumps(value, default=str)
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError('client_context is not serializable.') from exc
        if len(raw) > 12_000:
            raise serializers.ValidationError('client_context is too large.')
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
            raise serializers.ValidationError(
                user_message_for_code(ACCESS_CODE_USER_DISABLED),
                code=ACCESS_CODE_USER_DISABLED,
            )

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
    access = serializers.SerializerMethodField()
    kyc_verification = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()
    profile_sync_pending = serializers.SerializerMethodField()
    legacy_user_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'user_id', 'legacy_user_id', 'member_number', 'member_id', 'display_code',
            'phone', 'email', 'first_name', 'last_name',
            'role', 'is_active', 'is_restricted', 'payments_locked',
            'pay_in_allowed_when_disabled', 'allow_concurrent_sessions', 'access', 'profile',
            'created_at', 'onboarding', 'kyc_verification', 'profile_sync_pending',
        ]
        read_only_fields = [
            'id', 'user_id', 'legacy_user_id', 'member_number', 'member_id', 'display_code',
            'created_at', 'is_restricted', 'payments_locked',
            'pay_in_allowed_when_disabled', 'allow_concurrent_sessions', 'access',
            'kyc_verification', 'profile', 'profile_sync_pending',
        ]

    def get_legacy_user_id(self, obj):
        return getattr(obj, 'user_id', None) or ''

    def get_access(self, obj):
        from apps.core.financial_access import user_access_flags_snapshot

        return user_access_flags_snapshot(obj)

    def get_profile(self, obj):
        from apps.users.serializers import UserProfileSerializer

        try:
            return UserProfileSerializer(obj.profile).data
        except Exception:
            return None

    def get_kyc_verification(self, obj):
        from apps.users.kyc_display import build_kyc_verification_payload
        from apps.users.models import KYC

        kyc = KYC.objects.filter(user=obj).first()
        return build_kyc_verification_payload(kyc)

    def get_profile_sync_pending(self, obj):
        from apps.users.kyc_profile_sync_audit import get_pending_audits_for_user, serialize_pending_audit

        pending = get_pending_audits_for_user(obj)
        return [serialize_pending_audit(row) for row in pending[:5]]

    def get_onboarding(self, obj):
        from apps.users.models import KYC

        kyc = KYC.objects.filter(user=obj).first()
        pan_ok = bool(kyc and kyc.pan_verified)
        ad_ok = bool(kyc and kyc.aadhaar_verified)
        provider_complete = pan_ok and ad_ok
        status = kyc.verification_status if kyc else 'pending'
        # Active KYC requires Admin verification — provider checks alone are insufficient.
        kyc_complete = bool(kyc and status == 'verified')
        awaiting_admin_approval = bool(
            kyc and status == 'awaiting_approval' and provider_complete
        )
        has_mpin = bool(obj.mpin_hash)
        return {
            'kyc_status': status,
            'kyc_complete': kyc_complete,
            'provider_kyc_complete': provider_complete,
            'awaiting_admin_approval': awaiting_admin_approval,
            'kyc_rejected': status == 'rejected',
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
    name = serializers.CharField(max_length=200, min_length=2, trim_whitespace=True)

    def validate_name(self, value):
        cleaned = str(value or '').strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError('Name as per PAN is required.')
        return cleaned


class OnboardingDigilockerInitSerializer(serializers.Serializer):
    aadhaar = serializers.CharField(max_length=12, required=False, allow_blank=True)


class OnboardingDigilockerStatusSerializer(serializers.Serializer):
    verification_id = serializers.CharField(max_length=50)


class OnboardingDigilockerCompleteSerializer(serializers.Serializer):
    verification_id = serializers.CharField(max_length=50)


class ProfileSyncTokenSerializer(serializers.Serializer):
    sync_token = serializers.CharField(max_length=64)


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
