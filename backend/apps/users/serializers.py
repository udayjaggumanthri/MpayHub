"""
Serializers for users app.
"""
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from apps.authentication.models import User
from apps.users.services import assert_admin_may_deactivate_user
from apps.users.models import UserProfile, KYC, UserHierarchy
from apps.users.services import build_user_lineage
from apps.core.utils import (
    validate_phone, validate_email, validate_pan, validate_aadhaar,
)
from apps.core.exceptions import InvalidUserRole


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile."""
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'first_name', 'last_name', 'alternate_phone',
            'business_name', 'business_address', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class KYCSerializer(serializers.ModelSerializer):
    """Full KYC payload (identifiers visible). Restrict to Admin-facing detail responses."""

    class Meta:
        model = KYC
        fields = [
            'id', 'pan', 'pan_verified', 'pan_verified_at',
            'aadhaar', 'aadhaar_verified', 'aadhaar_verified_at',
            'verification_status', 'created_at'
        ]
        read_only_fields = [
            'id', 'pan', 'aadhaar',
            'pan_verified', 'pan_verified_at',
            'aadhaar_verified', 'aadhaar_verified_at',
            'verification_status', 'created_at',
        ]


class KYCListSerializer(serializers.ModelSerializer):
    """List views: verification flags only (no raw PAN/Aadhaar)."""

    class Meta:
        model = KYC
        fields = ['pan_verified', 'aadhaar_verified', 'verification_status']
        read_only_fields = fields


class KYCMaskedSerializer(serializers.ModelSerializer):
    """Non-Admin detail: masked PAN/Aadhaar."""

    pan = serializers.SerializerMethodField()
    aadhaar = serializers.SerializerMethodField()

    class Meta:
        model = KYC
        fields = [
            'id', 'pan', 'pan_verified', 'pan_verified_at',
            'aadhaar', 'aadhaar_verified', 'aadhaar_verified_at',
            'verification_status', 'created_at'
        ]
        read_only_fields = fields

    def get_pan(self, obj):
        if not obj.pan:
            return None
        p = str(obj.pan).upper()
        if len(p) <= 4:
            return '****'
        return f"{p[:2]}****{p[-2:]}"

    def get_aadhaar(self, obj):
        if not obj.aadhaar:
            return None
        a = str(obj.aadhaar)
        if len(a) <= 8:
            return '****'
        return f"{a[:4]}****{a[-4:]}"


class UserCreateSerializer(serializers.Serializer):
    """Serializer for creating new users. Accepts both camelCase and snake_case."""
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=10)
    alternate_phone = serializers.CharField(max_length=10, required=False, allow_blank=True)
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)
    business_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    business_address = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=128)
    mpin = serializers.CharField(max_length=6, write_only=True, required=False, allow_blank=True)
    pan = serializers.CharField(max_length=10, required=False, allow_blank=True)
    aadhaar = serializers.CharField(max_length=12, required=False, allow_blank=True)
    
    def to_internal_value(self, data):
        """Convert camelCase to snake_case for compatibility."""
        # Field mapping: camelCase -> snake_case
        field_mapping = {
            'firstName': 'first_name',
            'lastName': 'last_name',
            'alternatePhone': 'alternate_phone',
            'businessName': 'business_name',
            'businessAddress': 'business_address',
        }
        
        # Convert camelCase keys to snake_case
        # Prefer snake_case if both are provided
        normalized_data = {}
        for key, value in data.items():
            if key in field_mapping:
                snake_key = field_mapping[key]
                # Only use camelCase value if snake_case version doesn't exist
                if snake_key not in normalized_data:
                    normalized_data[snake_key] = value
            else:
                normalized_data[key] = value
        
        return super().to_internal_value(normalized_data)
    
    def validate_phone(self, value):
        """Validate phone number."""
        if not validate_phone(value):
            raise serializers.ValidationError("Invalid phone number format.")
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Phone number already registered.")
        return value
    
    def validate_email(self, value):
        """Validate email."""
        if not validate_email(value):
            raise serializers.ValidationError("Invalid email format.")
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value
    
    def validate_role(self, value):
        """Validate role based on current user's permissions."""
        request = self.context.get('request')
        if request and request.user:
            if not UserHierarchy.can_create_role(request.user, value):
                raise InvalidUserRole(f"You cannot create users with role: {value}")
        return value

    def validate_password(self, value):
        """Optional; if provided must be at least 8 characters."""
        if value in (None, ''):
            return ''
        if len(value) < 8:
            raise serializers.ValidationError('Password must be at least 8 characters.')
        return value
    
    def validate_mpin(self, value):
        """Optional at hierarchy onboarding — user sets MPIN after KYC."""
        if value in (None, ''):
            return ''
        if len(value) != 6 or not value.isdigit():
            raise serializers.ValidationError("MPIN must be exactly 6 digits.")
        return value

    def validate_pan(self, value):
        """Validate optional PAN format and uniqueness."""
        if not value:
            return value

        normalized_pan = value.upper().strip()
        if not validate_pan(normalized_pan):
            raise serializers.ValidationError("Invalid PAN format.")

        if KYC.objects.filter(pan=normalized_pan).exists():
            raise serializers.ValidationError("PAN already exists for another user.")

        return normalized_pan

    def validate_aadhaar(self, value):
        """Validate optional Aadhaar format and uniqueness."""
        if not value:
            return value

        normalized_aadhaar = value.strip()
        if not validate_aadhaar(normalized_aadhaar):
            raise serializers.ValidationError("Invalid Aadhaar format.")

        if KYC.objects.filter(aadhaar=normalized_aadhaar).exists():
            raise serializers.ValidationError("Aadhaar already exists for another user.")

        return normalized_aadhaar
    
    def validate(self, attrs):
        """Normalize optional MPIN."""
        if attrs.get('mpin') in (None, ''):
            attrs['mpin'] = ''
        if attrs.get('password') in (None, ''):
            attrs.pop('password', None)
        return attrs


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating users. Accepts both camelCase and snake_case."""
    alternate_phone = serializers.CharField(max_length=10, required=False, allow_blank=True)
    business_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    business_address = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8, required=False)
    mpin = serializers.CharField(max_length=6, write_only=True, required=False)
    is_active = serializers.BooleanField(required=False)
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'alternate_phone',
            'business_name', 'business_address', 'password', 'mpin', 'is_active'
        ]
    
    def to_internal_value(self, data):
        """Convert camelCase to snake_case for compatibility."""
        field_mapping = {
            'firstName': 'first_name',
            'lastName': 'last_name',
            'alternatePhone': 'alternate_phone',
            'businessName': 'business_name',
            'businessAddress': 'business_address',
        }
        
        normalized_data = {}
        for key, value in data.items():
            if key in field_mapping:
                snake_key = field_mapping[key]
                if snake_key not in normalized_data:
                    normalized_data[snake_key] = value
            else:
                normalized_data[key] = value
        
        return super().to_internal_value(normalized_data)
    
    def validate_email(self, value):
        """Validate email uniqueness (excluding current user)."""
        if not validate_email(value):
            raise serializers.ValidationError("Invalid email format.")
        # Check if email is already taken by another user
        user = self.instance
        if User.objects.filter(email=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("Email already registered.")
        return value
    
    def validate_password(self, value):
        """Validate password if provided."""
        if value and len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters.")
        return value
    
    def validate_mpin(self, value):
        """Validate MPIN if provided."""
        if value and (len(value) != 6 or not value.isdigit()):
            raise serializers.ValidationError("MPIN must be 6 digits.")
        return value

    def validate(self, attrs):
        """Credential and account state changes are Admin-only (prevents hierarchy takeover)."""
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        if user and user.is_authenticated and getattr(user, 'role', None) != 'Admin':
            for field in ('password', 'mpin', 'is_active'):
                if field in attrs:
                    raise serializers.ValidationError(
                        {field: 'Only administrators may change this field.'}
                    )
        if attrs.get('is_active') is False and self.instance:
            try:
                assert_admin_may_deactivate_user(actor=user, target=self.instance)
            except ValueError as e:
                raise serializers.ValidationError({'is_active': str(e)}) from e
        return attrs

    def update(self, instance, validated_data):
        """Update user and related profile."""
        # Extract fields for User model
        password = validated_data.pop('password', None)
        mpin = validated_data.pop('mpin', None)
        is_active = validated_data.pop('is_active', None)
        
        # Extract fields for UserProfile
        profile_data = {}
        profile_fields = ['alternate_phone', 'business_name', 'business_address']
        for field in profile_fields:
            if field in validated_data:
                profile_data[field] = validated_data.pop(field)
        
        # Update User model
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        if is_active is not None:
            instance.is_active = is_active
        
        instance.save()
        
        # Update UserProfile
        if profile_data:
            profile, created = UserProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        
        # Update MPIN if provided
        if mpin:
            instance.set_mpin(mpin)
        
        return instance


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for listing users."""
    profile = serializers.SerializerMethodField()
    kyc = serializers.SerializerMethodField()
    mpin_configured = serializers.SerializerMethodField()

    def get_profile(self, obj):
        try:
            return UserProfileSerializer(obj.profile).data
        except ObjectDoesNotExist:
            return None

    def get_kyc(self, obj):
        try:
            return KYCListSerializer(obj.kyc).data
        except ObjectDoesNotExist:
            return None

    def get_mpin_configured(self, obj):
        return bool(obj.mpin_hash)

    class Meta:
        model = User
        fields = [
            'id', 'user_id', 'phone', 'email', 'first_name', 'last_name',
            'role', 'is_active', 'profile', 'kyc', 'mpin_configured', 'created_at',
        ]
        read_only_fields = ['id', 'user_id', 'created_at']


class UserRoleChangeSerializer(serializers.Serializer):
    """Admin-only body for PATCH .../users/{id}/role/."""

    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)


class UserActiveStatusSerializer(serializers.Serializer):
    """Admin-only body for PATCH .../users/{id}/active-status/."""

    is_active = serializers.BooleanField()

    def validate(self, attrs):
        request = self.context.get('request')
        target = self.context.get('target')
        actor = getattr(request, 'user', None) if request else None
        if attrs.get('is_active') is False and target and actor:
            try:
                assert_admin_may_deactivate_user(actor=actor, target=target)
            except ValueError as e:
                raise serializers.ValidationError({'is_active': str(e)}) from e
        return attrs


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer for user details."""
    profile = serializers.SerializerMethodField()
    kyc = serializers.SerializerMethodField()
    hierarchy_lineage = serializers.SerializerMethodField()
    mpin_configured = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'user_id', 'phone', 'email', 'first_name', 'last_name',
            'role', 'is_active', 'profile', 'kyc', 'hierarchy_lineage',
            'mpin_configured', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user_id', 'created_at', 'updated_at', 'hierarchy_lineage']

    def get_mpin_configured(self, obj):
        return bool(obj.mpin_hash)

    def get_profile(self, obj):
        try:
            return UserProfileSerializer(obj.profile).data
        except ObjectDoesNotExist:
            return None

    def get_kyc(self, obj):
        try:
            kyc = obj.kyc
        except ObjectDoesNotExist:
            return None
        request = self.context.get('request')
        if request and getattr(request.user, 'is_authenticated', False) and getattr(
            request.user, 'role', None
        ) == 'Admin':
            return KYCSerializer(kyc).data
        return KYCMaskedSerializer(kyc).data

    def get_hierarchy_lineage(self, obj):
        return build_user_lineage(obj)


class PANVerificationSerializer(serializers.Serializer):
    """Serializer for PAN verification."""
    pan = serializers.CharField(max_length=10)
    
    def validate_pan(self, value):
        """Validate PAN format."""
        if not validate_pan(value):
            raise serializers.ValidationError("Invalid PAN format.")
        return value


class AadhaarOTPSerializer(serializers.Serializer):
    """Serializer for sending Aadhaar OTP."""
    aadhaar = serializers.CharField(max_length=12)
    
    def validate_aadhaar(self, value):
        """Validate Aadhaar format."""
        if not validate_aadhaar(value):
            raise serializers.ValidationError("Invalid Aadhaar format.")
        return value


class AadhaarOTPVerificationSerializer(serializers.Serializer):
    """Serializer for verifying Aadhaar OTP."""
    aadhaar = serializers.CharField(max_length=12)
    otp = serializers.CharField(max_length=6)
    
    def validate_aadhaar(self, value):
        """Validate Aadhaar format."""
        if not validate_aadhaar(value):
            raise serializers.ValidationError("Invalid Aadhaar format.")
        return value
