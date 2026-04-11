"""
Fund management models for Load Money and Payout.
"""
from decimal import Decimal

from django.db import models

from apps.core.models import BaseModel
from apps.authentication.models import User
from apps.bank_accounts.models import BankAccount


class PayInPackage(BaseModel):
    """
    Admin-configurable pay-in package (gateway + fee profile).
    Percentages are applied to gross principal (₹1,00,000 → 1% = ₹1,000).
    """

    PROVIDER_CHOICES = [
        ('razorpay', 'Razorpay'),
        ('payu', 'PayU'),
        ('mock', 'Mock / Dev'),
    ]

    code = models.SlugField(max_length=80, unique=True, db_index=True)
    display_name = models.CharField(max_length=200)
    payment_gateway = models.ForeignKey(
        'admin_panel.PaymentGateway',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pay_in_packages',
    )
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='mock',
        db_index=True,
    )
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1'))
    max_amount_per_txn = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('200000'))
    gateway_fee_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('1'))
    admin_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.24'))
    super_distributor_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.01'))
    master_distributor_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.02'))
    distributor_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.03'))
    retailer_commission_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.06'))
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'pay_in_packages'
        ordering = ['sort_order', 'display_name']

    def __str__(self):
        return f"{self.display_name} ({self.code})"


class LoadMoney(BaseModel):
    """
    Load Money transaction model.
    """

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='load_money_transactions',
        db_index=True,
    )
    package = models.ForeignKey(
        PayInPackage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='load_money_transactions',
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Gross pay-in amount (principal before deductions).',
    )
    gateway = models.CharField(max_length=100)
    charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text='Total system deduction (sum of gateway+admin+chain slices on principal).',
    )
    net_credit = models.DecimalField(max_digits=12, decimal_places=2)
    fee_breakdown_snapshot = models.JSONField(default=dict, blank=True)
    customer_name = models.CharField(max_length=200, blank=True, default='')
    customer_email = models.EmailField(blank=True, default='')
    customer_phone = models.CharField(max_length=10, blank=True, default='')
    provider_order_id = models.CharField(max_length=191, blank=True, null=True, db_index=True)
    provider_payment_id = models.CharField(max_length=191, blank=True, null=True, unique=True)
    payment_method = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text='Provider channel: upi, card, netbanking, wallet, etc.',
    )
    payment_meta = models.JSONField(
        default=dict,
        blank=True,
        help_text='Optional details from provider (e.g. card_type, network).',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    gateway_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'load_money'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status', 'created_at']),
            models.Index(fields=['transaction_id']),
        ]

    def __str__(self):
        return f"{self.transaction_id} - {self.user.user_id} - ₹{self.amount}"


class Payout(BaseModel):
    """
    Payout transaction model.
    """

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]

    TRANSFER_MODE_CHOICES = [
        ('IMPS', 'IMPS'),
        ('NEFT', 'NEFT'),
        ('RTGS', 'RTGS'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payout_transactions',
        db_index=True,
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='payouts',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    charge = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    total_deducted = models.DecimalField(max_digits=12, decimal_places=2)
    transfer_mode = models.CharField(
        max_length=10,
        choices=TRANSFER_MODE_CHOICES,
        default='IMPS',
        db_index=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    gateway_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'payouts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status', 'created_at']),
            models.Index(fields=['transaction_id']),
        ]

    def __str__(self):
        return f"{self.transaction_id} - {self.user.user_id} - ₹{self.amount}"
