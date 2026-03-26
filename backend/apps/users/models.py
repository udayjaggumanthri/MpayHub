"""
User management models for the mPayhub platform.
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from apps.authentication.models import User


class UserProfile(BaseModel):
    """
    Extended user profile with business details.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    alternate_phone = models.CharField(max_length=10, blank=True, null=True)
    business_name = models.CharField(max_length=200, blank=True, null=True)
    business_address = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'user_profiles'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.user_id} - {self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class KYC(BaseModel):
    """
    KYC (Know Your Customer) information for users.
    """
    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='kyc'
    )
    pan = models.CharField(max_length=10, unique=True, db_index=True, blank=True, null=True)
    pan_verified = models.BooleanField(default=False)
    pan_verified_at = models.DateTimeField(null=True, blank=True)
    aadhaar = models.CharField(max_length=12, unique=True, db_index=True, blank=True, null=True)
    aadhaar_verified = models.BooleanField(default=False)
    aadhaar_verified_at = models.DateTimeField(null=True, blank=True)
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default='pending'
    )
    
    class Meta:
        db_table = 'kyc'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"KYC for {self.user.user_id}"


class UserHierarchy(BaseModel):
    """
    User hierarchy model to track parent-child relationships.
    Admin → Master Distributor → Distributor → Retailer
    """
    parent_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='children',
        db_index=True
    )
    child_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='parents',
        db_index=True
    )
    
    class Meta:
        db_table = 'user_hierarchy'
        unique_together = [['parent_user', 'child_user']]
        indexes = [
            models.Index(fields=['parent_user', 'child_user']),
        ]
    
    def __str__(self):
        return f"{self.parent_user.user_id} → {self.child_user.user_id}"
    
    @classmethod
    def can_create_role(cls, parent_user, target_role):
        """
        Check if parent_user can create a user with target_role.
        """
        role_hierarchy = {
            'Admin': ['Master Distributor', 'Distributor', 'Retailer'],
            'Master Distributor': ['Distributor', 'Retailer'],
            'Distributor': ['Retailer'],
            'Retailer': []
        }
        return target_role in role_hierarchy.get(parent_user.role, [])
    
    @classmethod
    def get_subordinates(cls, user):
        """
        Get all subordinate users (direct and indirect).
        """
        subordinates = []
        direct_children = cls.objects.filter(parent_user=user).select_related('child_user')
        
        for hierarchy in direct_children:
            child = hierarchy.child_user
            subordinates.append(child)
            # Recursively get children of children
            subordinates.extend(cls.get_subordinates(child))
        
        return subordinates
