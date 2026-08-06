"""
Admin wallet adjustment audit model.

Append-only records for every manual credit/debit performed by an Admin.
Money movement itself reuses Wallet.credit/debit + PassbookEntry; this table
is the dedicated reportable audit trail with mandatory documentation.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.authentication.models import User


class WalletAdjustment(BaseModel):
    """Dedicated audit record for an admin wallet adjustment."""

    WALLET_TYPE_CHOICES = [
        ('main', 'Main Wallet'),
        ('bbps', 'BBPS Wallet'),
    ]

    ADJUSTMENT_TYPE_CHOICES = [
        ('CREDIT', 'Credit'),
        ('DEBIT', 'Debit'),
    ]

    REASON_CATEGORY_CHOICES = [
        ('failed_transaction', 'Failed transaction'),
        ('amount_not_reflected', 'Amount not reflected'),
        ('transaction_mismatch', 'Transaction mismatch'),
        ('refund_reversal', 'Refund / reversal'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]

    adjustment_id = models.CharField(max_length=32, unique=True, db_index=True)
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='wallet_adjustments',
        db_index=True,
        help_text='Target user whose wallet was adjusted.',
    )
    wallet_type = models.CharField(max_length=20, choices=WALLET_TYPE_CHOICES, db_index=True)
    adjustment_type = models.CharField(
        max_length=10,
        choices=ADJUSTMENT_TYPE_CHOICES,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=18, decimal_places=4)

    reference_number = models.CharField(
        max_length=100,
        db_index=True,
        help_text='Original transaction reference / UTR / service id being corrected.',
    )
    reason_category = models.CharField(max_length=40, choices=REASON_CATEGORY_CHOICES)
    remarks = models.TextField(help_text='Mandatory free-text justification.')

    balance_before = models.DecimalField(max_digits=18, decimal_places=4)
    balance_after = models.DecimalField(max_digits=18, decimal_places=4)

    passbook_entry = models.ForeignKey(
        'transactions.PassbookEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_adjustments',
    )
    wallet_transaction = models.ForeignKey(
        'wallets.WalletTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_adjustments',
    )

    adjusted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_adjustments_performed',
    )
    adjusted_by_name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Immutable display name of the admin at time of adjustment.',
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='SUCCESS',
        db_index=True,
    )
    failure_reason = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'wallet_adjustments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['adjustment_type', 'created_at']),
            models.Index(fields=['reference_number']),
            models.Index(fields=['wallet_type', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'reference_number', 'adjustment_type'],
                condition=models.Q(is_deleted=False, status='SUCCESS'),
                name='uniq_wallet_adj_user_ref_type_success',
            ),
        ]

    def __str__(self):
        return f'{self.adjustment_id} {self.adjustment_type} ₹{self.amount} → {self.user_id}'
