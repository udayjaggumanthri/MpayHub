"""
Serializers for authentication app.
"""
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils import timezone
from datetime import timedelta
from apps.authentication.models import User, OTP, UserSession
from apps.core.utils import generate_otp, validate_phone, validate_mpin
from apps.core.exceptions import InvalidCredentials, InvalidMPIN, InvalidOTP
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
        
        user = authenticate(username=phone, password=password)
        if not user:
            raise InvalidCredentials("Invalid phone number or password.")
        
        if not user.is_active:
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

        if not user.is_active:
            raise serializers.ValidationError('This account has been disabled. Contact support.')

        if not user.check_mpin(mpin):
            raise InvalidMPIN("Invalid MPIN.")

        return attrs


class SendOTPSerializer(serializers.Serializer):
    """Serializer for sending OTP."""
    phone = serializers.CharField(max_length=10)
    purpose = serializers.ChoiceField(choices=OTP.PURPOSE_CHOICES, default='password-reset')
    
    def validate_phone(self, value):
        """Validate phone number."""
        if not validate_phone(value):
            raise serializers.ValidationError("Invalid phone number format.")
        return value


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
        """Verify OTP."""
        phone = attrs.get('phone')
        code = attrs.get('code')
        purpose = attrs.get('purpose')
        
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
            
            attrs['otp'] = otp
            return attrs
        except OTP.DoesNotExist:
            raise InvalidOTP("OTP not found or already used.")


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
        
        # Verify OTP
        phone = attrs.get('phone')
        otp_code = attrs.get('otp')
        
        try:
            otp = OTP.objects.filter(
                phone=phone,
                purpose='password-reset',
                is_used=False
            ).latest('created_at')
            
            if not otp.is_valid():
                raise InvalidOTP("OTP has expired or already used.")
            
            if otp.code != otp_code:
                raise InvalidOTP("Invalid OTP code.")
            
            attrs['otp'] = otp
            return attrs
        except OTP.DoesNotExist:
            raise InvalidOTP("OTP not found or already used.")


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model (login /me). Includes onboarding gate for hierarchy-created users."""

    onboarding = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'user_id', 'phone', 'email', 'first_name', 'last_name',
            'role', 'is_active', 'created_at', 'onboarding',
        ]
        read_only_fields = ['id', 'user_id', 'created_at']

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
        }


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
