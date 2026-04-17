"""
Transaction and reporting models for the mPayhub platform.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.authentication.models import User

MONEY_MAX_DIGITS = 18
MONEY_DECIMAL_PLACES = 4


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

    SERVICE_FAMILY_CHOICES = [
        ('payin', 'Pay-in'),
        ('payout', 'Payout'),
        ('bbps', 'BBPS'),
        ('wallet_transfer', 'Wallet transfer'),
        ('commission', 'Commission'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='transactions',
        db_index=True,
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, db_index=True)
    amount = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES)
    charge = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0)
    platform_fee = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0, null=True, blank=True
    )
    net_amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    service_id = models.CharField(max_length=100, unique=True, db_index=True)
    request_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    reference = models.CharField(max_length=255, blank=True, null=True)
    # BBPS specific fields
    bill_type = models.CharField(max_length=50, blank=True, null=True)
    biller = models.CharField(max_length=200, blank=True, null=True)

    # Enterprise reporting dimensions
    agent_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agent_transactions',
        help_text='Actor / wallet owner snapshot for reporting.',
    )
    agent_role_at_time = models.CharField(max_length=50, blank=True, default='')
    agent_user_code = models.CharField(max_length=30, blank=True, default='', db_index=True)
    agent_name_snapshot = models.CharField(max_length=255, blank=True, default='')
    service_family = models.CharField(
        max_length=32,
        choices=SERVICE_FAMILY_CHOICES,
        blank=True,
        default='',
        db_index=True,
    )
    bank_txn_id = models.CharField(max_length=191, blank=True, null=True)
    card_last4 = models.CharField(max_length=4, blank=True, null=True)

    class Meta:
        db_table = 'transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'transaction_type', 'status', 'created_at']),
            models.Index(fields=['transaction_type', 'created_at']),
            models.Index(fields=['agent_user_code', 'created_at']),
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
        ('profit', 'Profit'),
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
    debit_amount = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0)
    credit_amount = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0)
    opening_balance = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES)
    closing_balance = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES)
    service_charge = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=0,
        help_text='Fees/charges for this line (e.g. payout slab); 0 when N/A.',
    )
    principal_amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        null=True,
        blank=True,
        help_text='Underlying transaction amount excluding charge when applicable.',
    )

    initiator_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_passbook_entries',
        help_text='Business actor that caused this line (e.g. retailer on a commission credit).',
    )
    initiator_role_at_time = models.CharField(max_length=50, blank=True, default='')
    initiator_user_code = models.CharField(max_length=30, blank=True, default='', db_index=True)
    initiator_name_snapshot = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'passbook_entries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['user', 'wallet_type', 'created_at']),
            models.Index(fields=['service_id', 'created_at']),
        ]

    def __str__(self):
        return f"{self.service_id} - {self.user.user_id} - {self.service}"


class CommissionLedger(BaseModel):
    """
    Audit trail for commission credits (pay-in chain + retailer).
    """

    SOURCE_CHOICES = [
        ('payin', 'Pay-in'),
        ('profit', 'Platform profit'),
    ]

    WALLET_TYPE_CHOICES = [
        ('main', 'Main'),
        ('commission', 'Commission'),
        ('profit', 'Profit'),
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
    amount = models.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='payin', db_index=True)
    reference_service_id = models.CharField(max_length=100, db_index=True)
    wallet_type = models.CharField(max_length=20, choices=WALLET_TYPE_CHOICES, default='commission')
    meta = models.JSONField(default=dict, blank=True)

    source_user_code = models.CharField(max_length=30, blank=True, default='', db_index=True)
    source_role = models.CharField(max_length=50, blank=True, default='', db_index=True)
    source_name_snapshot = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'commission_ledger'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reference_service_id']),
            models.Index(fields=['user', 'source', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        uid = self.user_id or 'platform'
        return f"{self.reference_service_id} - {uid} - ₹{self.amount}"
