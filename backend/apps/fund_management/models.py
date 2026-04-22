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
    min_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('1'))
    max_amount_per_txn = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('200000'))
    gateway_fee_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('1'))
    admin_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.24'))
    super_distributor_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.01'))
    master_distributor_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.02'))
    distributor_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.03'))
    retailer_commission_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.06'))
    is_active = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(
        default=False,
        db_index=True,
        help_text='If true, this package is auto-assigned to new users. Only one package can be default.',
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'pay_in_packages'
        ordering = ['sort_order', 'display_name']

    def __str__(self):
        return f"{self.display_name} ({self.code})"

    def save(self, *args, **kwargs):
        if self.is_default:
            PayInPackage.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class PayoutSlabTier(BaseModel):
    """
    Per-package payout slab: flat charge for withdrawal amount in [min_amount, max_amount].
    max_amount null means unbounded upper range. Tiers are configured per PayInPackage
    so assignment grants both pay-in and payout rules.
    """

    package = models.ForeignKey(
        PayInPackage,
        on_delete=models.CASCADE,
        related_name='payout_slabs',
        db_index=True,
    )
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    min_amount = models.DecimalField(max_digits=18, decimal_places=4)
    max_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
        help_text='Inclusive upper bound; null = no upper limit.',
    )
    flat_charge = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = 'payout_slab_tiers'
        ordering = ['package_id', 'sort_order', 'min_amount']
        indexes = [
            models.Index(fields=['package', 'sort_order']),
        ]

    def __str__(self):
        upper = self.max_amount if self.max_amount is not None else '∞'
        return f"{self.package.code} [{self.min_amount}–{upper}]: ₹{self.flat_charge}"


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
        max_digits=18,
        decimal_places=4,
        help_text='Gross pay-in amount (principal before deductions).',
    )
    gateway = models.CharField(max_length=100)
    charge = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal('0'),
        help_text='Total system deduction (sum of gateway+admin+chain slices on principal).',
    )
    net_credit = models.DecimalField(max_digits=18, decimal_places=4)
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
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    charge = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    platform_fee = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    total_deducted = models.DecimalField(max_digits=18, decimal_places=4)
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


class UserPackageAssignment(BaseModel):
    """
    Links users to their assigned pay-in packages.
    Users can only access packages explicitly assigned to them.
    If no packages are assigned, the user falls back to the default package.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='package_assignments',
        db_index=True,
    )
    package = models.ForeignKey(
        PayInPackage,
        on_delete=models.CASCADE,
        related_name='user_assignments',
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='packages_assigned_to_others',
        help_text='The user who assigned this package (Admin or upline).',
    )

    class Meta:
        db_table = 'user_package_assignments'
        unique_together = ['user', 'package']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.user_id} -> {self.package.display_name}"
