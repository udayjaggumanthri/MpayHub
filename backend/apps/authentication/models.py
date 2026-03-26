"""
Authentication models for the mPayhub platform.
"""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from apps.core.models import TimestampedModel
from apps.core.utils import encrypt_mpin, decrypt_mpin


class UserManager(BaseUserManager):
    """Custom user manager for phone-based authentication."""
    
    def create_user(self, phone, email, password=None, **extra_fields):
        """Create and save a regular user with phone and email."""
        if not phone:
            raise ValueError('The phone field must be set')
        if not email:
            raise ValueError('The email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(phone=phone, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, phone, email, password=None, **extra_fields):
        """Create and save a superuser with phone and email."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'Admin')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(phone, email, password, **extra_fields)


class User(AbstractUser, TimestampedModel):
    """
    Custom User model extending Django's AbstractUser.
    """
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Master Distributor', 'Master Distributor'),
        ('Distributor', 'Distributor'),
        ('Retailer', 'Retailer'),
    ]
    
    username = None  # Remove username field
    phone = models.CharField(max_length=10, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Retailer')
    mpin_hash = models.CharField(max_length=255, blank=True, null=True)
    user_id = models.CharField(max_length=20, unique=True, db_index=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['email']
    
    objects = UserManager()
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user_id} - {self.get_full_name() or self.phone}"
    
    def set_mpin(self, mpin):
        """Set and encrypt MPIN."""
        self.mpin_hash = encrypt_mpin(mpin)
        self.save(update_fields=['mpin_hash'])
    
    def check_mpin(self, mpin):
        """Check if provided MPIN matches stored MPIN."""
        if not self.mpin_hash:
            return False
        try:
            decrypted_mpin = decrypt_mpin(self.mpin_hash)
            return decrypted_mpin == mpin
        except Exception:
            return False


class OTP(TimestampedModel):
    """
    OTP model for password reset and verification.
    """
    PURPOSE_CHOICES = [
        ('password-reset', 'Password Reset'),
        ('aadhaar-verification', 'Aadhaar Verification'),
    ]
    
    phone = models.CharField(max_length=10, db_index=True)
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default='password-reset')
    expires_at = models.DateTimeField(db_index=True)
    is_used = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'otps'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone', 'purpose', 'is_used']),
        ]
    
    def __str__(self):
        return f"OTP for {self.phone} - {self.purpose}"
    
    def is_valid(self):
        """Check if OTP is valid (not used and not expired)."""
        return not self.is_used and timezone.now() < self.expires_at
    
    def mark_as_used(self):
        """Mark OTP as used."""
        self.is_used = True
        self.save(update_fields=['is_used'])


class UserSession(TimestampedModel):
    """
    User session model for tracking active sessions.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    token = models.CharField(max_length=255, db_index=True)
    device_info = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"Session for {self.user.user_id}"
    
    def is_valid(self):
        """Check if session is valid."""
        return self.is_active and timezone.now() < self.expires_at
