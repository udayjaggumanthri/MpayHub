"""
Serializers for users app.
"""
from rest_framework import serializers
from apps.authentication.models import User
from apps.users.models import UserProfile, KYC, UserHierarchy
from apps.core.utils import (
    validate_phone, validate_email, validate_pan, validate_aadhaar,
    generate_user_id
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
    """Serializer for KYC."""
    
    class Meta:
        model = KYC
        fields = [
            'id', 'pan', 'pan_verified', 'pan_verified_at',
            'aadhaar', 'aadhaar_verified', 'aadhaar_verified_at',
            'verification_status', 'created_at'
        ]
        read_only_fields = [
            'id', 'pan_verified', 'pan_verified_at',
            'aadhaar_verified', 'aadhaar_verified_at',
            'verification_status', 'created_at'
        ]


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
    password = serializers.CharField(write_only=True, min_length=8)
    mpin = serializers.CharField(max_length=6, write_only=True, required=True, min_length=6)
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
    
    def validate_mpin(self, value):
        """Validate MPIN - mandatory field."""
        if not value:
            raise serializers.ValidationError("MPIN is required and cannot be blank.")
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
        """Validate and ensure MPIN is provided."""
        # MPIN is mandatory
        if 'mpin' not in attrs or not attrs.get('mpin'):
            raise serializers.ValidationError({"mpin": "MPIN is required and cannot be blank."})
        
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
    profile = UserProfileSerializer(read_only=True)
    kyc = KYCSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'user_id', 'phone', 'email', 'first_name', 'last_name',
            'role', 'is_active', 'profile', 'kyc', 'created_at'
        ]
        read_only_fields = ['id', 'user_id', 'created_at']


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer for user details."""
    profile = UserProfileSerializer(read_only=True)
    kyc = KYCSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'user_id', 'phone', 'email', 'first_name', 'last_name',
            'role', 'is_active', 'profile', 'kyc', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user_id', 'created_at', 'updated_at']


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
