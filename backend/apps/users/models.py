"""
User management models for the mPayhub platform.
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from apps.authentication.models import User
from apps.users.hierarchy_policy import can_parent_create_child, creatable_roles_for


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
    date_of_birth = models.DateField(blank=True, null=True)
    
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

    Lifecycle:
      pending → (PAN + Aadhaar provider-verified) → awaiting_approval
      → Admin approve → verified | Admin reject → rejected
    Account readiness (onboarding.kyc_complete / account_ready) requires verified.
    """
    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('awaiting_approval', 'Awaiting Approval'),
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
        default='pending',
        db_index=True,
    )
    verified_identity = models.JSONField(default=dict, blank=True)
    # Admin decision metadata (denormalized for list/filter; history in KycApprovalAudit)
    decided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kyc_decisions',
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'kyc'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"KYC for {self.user.user_id}"

    @property
    def provider_complete(self):
        """True when both identity providers have verified documents."""
        return bool(self.pan_verified and self.aadhaar_verified)

    @property
    def awaiting_admin_approval(self):
        return self.verification_status == 'awaiting_approval' and self.provider_complete

    @property
    def is_admin_verified(self):
        return self.verification_status == 'verified'


class KycVerificationAttempt(BaseModel):
    """Audit trail for external PAN verification calls."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kyc_pan_attempts')
    provider_code = models.CharField(max_length=80, blank=True, default='')
    verification_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    reference_id = models.CharField(max_length=50, blank=True, default='')
    status = models.CharField(max_length=40, blank=True, default='')
    request_meta = models.JSONField(default=dict, blank=True)
    response_meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'kyc_verification_attempts'
        ordering = ['-created_at']


class KycDigilockerSession(BaseModel):
    """Tracks Cashfree DigiLocker consent sessions across redirect."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kyc_digilocker_sessions')
    verification_id = models.CharField(max_length=50, unique=True, db_index=True)
    reference_id = models.CharField(max_length=50, blank=True, default='')
    status = models.CharField(max_length=30, blank=True, default='PENDING', db_index=True)
    user_flow = models.CharField(max_length=20, blank=True, default='')
    document_requested = models.JSONField(default=list, blank=True)
    provider_code = models.CharField(max_length=80, blank=True, default='')
    raw_status = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'kyc_digilocker_sessions'
        ordering = ['-created_at']


class KycApprovalAudit(BaseModel):
    """
    Immutable audit trail for Admin KYC approve/reject decisions.
    Supports replay, compliance review, and future multi-step approval chains.
    """
    DECISION_CHOICES = [
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kyc_approval_audits')
    kyc = models.ForeignKey(KYC, on_delete=models.CASCADE, related_name='approval_audits')
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES, db_index=True)
    previous_status = models.CharField(max_length=20, blank=True, default='')
    new_status = models.CharField(max_length=20, blank=True, default='')
    decided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kyc_approval_actions',
    )
    notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'kyc_approval_audits'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['decision', 'created_at']),
        ]

    def __str__(self):
        return f"KYC {self.decision} for {self.user_id} by {self.decided_by_id}"


class KycProfileSyncAudit(BaseModel):
    """Immutable audit trail for KYC → profile synchronization."""

    STATUS_CHOICES = [
        ('pending', 'Pending confirmation'),
        ('applied', 'Applied after confirmation'),
        ('auto_applied', 'Auto-applied'),
        ('declined', 'Declined by user'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kyc_profile_sync_audits')
    source = models.CharField(max_length=20, blank=True, default='')  # pan | aadhaar
    trigger = models.CharField(max_length=40, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)

    before_first_name = models.CharField(max_length=150, blank=True, default='')
    before_last_name = models.CharField(max_length=150, blank=True, default='')
    before_date_of_birth = models.DateField(null=True, blank=True)

    verified_full_name = models.CharField(max_length=300, blank=True, default='')
    verified_date_of_birth = models.DateField(null=True, blank=True)

    after_first_name = models.CharField(max_length=150, blank=True, default='')
    after_last_name = models.CharField(max_length=150, blank=True, default='')
    after_date_of_birth = models.DateField(null=True, blank=True)

    sync_token = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    sync_token_expires_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    actor_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='kyc_profile_sync_actions',
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'kyc_profile_sync_audits'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status', '-created_at']),
        ]

    def __str__(self):
        return f'KYC profile sync {self.status} for {self.user_id}'


class UserHierarchy(BaseModel):
    """
    User hierarchy model to track parent-child relationships.
    Admin → Super Distributor → Master Distributor → Distributor → Retailer
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
    def can_parent_role_create_child_role(cls, parent_role: str, child_role: str) -> bool:
        """Whether a user with parent_role may have a direct report with child_role."""
        return can_parent_create_child(parent_role, child_role)

    @classmethod
    def creatable_roles_for_parent(cls, parent_role: str) -> list[str]:
        return creatable_roles_for(parent_role)

    @classmethod
    def can_create_role(cls, parent_user, target_role):
        """
        Check if parent_user can create a user with target_role.
        """
        return cls.can_parent_role_create_child_role(getattr(parent_user, 'role', None), target_role)
    
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
