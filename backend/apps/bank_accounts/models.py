"""
Bank account models for the mPayhub platform.
"""
from django.db import models
from apps.core.models import BaseModel
from apps.authentication.models import User
from apps.contacts.models import Contact


class BankAccount(BaseModel):
    """
    Bank account model.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bank_accounts',
        db_index=True
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        related_name='bank_accounts',
        null=True,
        blank=True
    )
    account_number = models.CharField(max_length=20, db_index=True)
    ifsc = models.CharField(max_length=11)
    bank_name = models.CharField(max_length=200)
    account_holder_name = models.CharField(max_length=200)
    beneficiary_name = models.CharField(max_length=200, blank=True, null=True)
    mobile_number = models.CharField(max_length=10, blank=True, default='', db_index=True)
    is_verified = models.BooleanField(default=False)
    verification_reference_id = models.CharField(max_length=50, blank=True, default='')
    provider_code = models.CharField(max_length=80, blank=True, default='')
    branch = models.CharField(max_length=200, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    name_match_score = models.CharField(max_length=20, blank=True, default='')
    name_match_result = models.CharField(max_length=50, blank=True, default='')
    verification_details = models.JSONField(default=dict, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'bank_accounts'
        unique_together = [['user', 'account_number', 'ifsc']]
        indexes = [
            models.Index(fields=['user', 'account_number']),
        ]
    
    def __str__(self):
        return f"{self.account_holder_name} - {self.account_number[-4:]}"


class BankVerificationAttempt(BaseModel):
    """Audit trail for external bank account verification calls."""

    STATUS_CHOICES = [
        ('validated', 'Validated'),
        ('failed', 'Failed'),
        ('consumed', 'Consumed'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bank_verification_attempts',
    )
    provider_code = models.CharField(max_length=80, blank=True, default='')
    reference_id = models.CharField(max_length=50, blank=True, default='')
    account_number_last4 = models.CharField(max_length=4, blank=True, default='')
    ifsc = models.CharField(max_length=11, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True, default='')
    validation_token = models.CharField(max_length=64, blank=True, default='', db_index=True)
    validation_token_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    request_meta = models.JSONField(default=dict, blank=True)
    response_meta = models.JSONField(default=dict, blank=True)
    wallet_charged = models.BooleanField(default=False)
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        related_name='verification_attempts',
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'bank_verification_attempts'
        ordering = ['-created_at']
