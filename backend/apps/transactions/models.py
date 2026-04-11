"""
Transaction and reporting models for the mPayhub platform.
"""
from django.db import models
from decimal import Decimal
from apps.core.models import BaseModel
from apps.authentication.models import User


class Transaction(BaseModel):
    """
    Transaction model for all types of transactions.
    """
    TRANSACTION_TYPE_CHOICES = [
        ('payin', 'Pay In'),
        ('payout', 'Pay Out'),
        ('bbps', 'BBPS'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='transactions',
        db_index=True
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    charge = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, null=True, blank=True)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    service_id = models.CharField(max_length=100, unique=True, db_index=True)
    request_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    reference = models.CharField(max_length=255, blank=True, null=True)
    # BBPS specific fields
    bill_type = models.CharField(max_length=50, blank=True, null=True)
    biller = models.CharField(max_length=200, blank=True, null=True)
    
    class Meta:
        db_table = 'transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'transaction_type', 'status', 'created_at']),
            models.Index(fields=['service_id']),
        ]
    
    def __str__(self):
        return f"{self.service_id} - {self.user.user_id} - {self.transaction_type}"


class PassbookEntry(BaseModel):
    """
    Passbook entry model for transaction history (SBI-style running balance).
    """

    WALLET_TYPE_CHOICES = [
        ('main', 'Main'),
        ('commission', 'Commission'),
        ('bbps', 'BBPS'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='passbook_entries',
        db_index=True,
    )
    wallet_type = models.CharField(
        max_length=20,
        choices=WALLET_TYPE_CHOICES,
        default='main',
        db_index=True,
        help_text='Which wallet this line applies to.',
    )
    service = models.CharField(max_length=100)
    service_id = models.CharField(max_length=100, db_index=True)
    description = models.TextField()
    debit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2)
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'passbook_entries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['user', 'wallet_type', 'created_at']),
            models.Index(fields=['service_id']),
        ]

    def __str__(self):
        return f"{self.service_id} - {self.user.user_id} - {self.service}"


class CommissionLedger(BaseModel):
    """
    Audit trail for commission credits (pay-in chain + retailer).
    """

    SOURCE_CHOICES = [
        ('payin', 'Pay-in'),
    ]

    WALLET_TYPE_CHOICES = [
        ('main', 'Main'),
        ('commission', 'Commission'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='commission_ledger_entries',
        null=True,
        blank=True,
        db_index=True,
        help_text='Null for rows absorbed by platform with no wallet user.',
    )
    role_at_time = models.CharField(max_length=50, blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='payin', db_index=True)
    reference_service_id = models.CharField(max_length=100, db_index=True)
    wallet_type = models.CharField(max_length=20, choices=WALLET_TYPE_CHOICES, default='commission')
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'commission_ledger'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reference_service_id']),
            models.Index(fields=['user', 'source', 'created_at']),
        ]

    def __str__(self):
        uid = self.user_id or 'platform'
        return f"{self.reference_service_id} - {uid} - ₹{self.amount}"
