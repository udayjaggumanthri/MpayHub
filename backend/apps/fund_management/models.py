"""
Fund management models for Load Money and Payout.
"""
import uuid
from decimal import Decimal

from django.core.validators import FileExtensionValidator
from django.db import models

from apps.core.models import BaseModel
from apps.authentication.models import User
from apps.bank_accounts.models import BankAccount


def payin_qr_image_upload_to(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'bin'
    return f'payin/qr/{uuid.uuid4().hex}.{ext}'


def payin_receipt_upload_to(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'bin'
    return f'payin/receipts/{uuid.uuid4().hex}.{ext}'


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
    retailer_commission_pct = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0'))
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


class PayInPackageGateway(BaseModel):
    """
    Many-to-many link: which payment gateways may execute pay-in for a package.
    Fee/commission rules remain on PayInPackage; this only selects the collection rail.
    """

    package = models.ForeignKey(
        PayInPackage,
        on_delete=models.CASCADE,
        related_name='package_gateways',
        db_index=True,
    )
    payment_gateway = models.ForeignKey(
        'admin_panel.PaymentGateway',
        on_delete=models.CASCADE,
        related_name='package_links',
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Suggested gateway when user does not choose one explicitly.',
    )
    sort_order = models.PositiveIntegerField(default=0)
    gateway_fee_pct = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text='Per-gateway fee on this package; null uses package.gateway_fee_pct.',
    )

    class Meta:
        db_table = 'pay_in_package_gateways'
        ordering = ['package_id', 'sort_order', 'id']
        unique_together = [['package', 'payment_gateway']]
        indexes = [
            models.Index(fields=['package', 'is_active', 'sort_order']),
        ]

    def __str__(self):
        return f'{self.package_id} -> {self.payment_gateway_id}'


class PayInQrAccount(BaseModel):
    """Admin-managed UPI QR collection account for manual pay-in."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    display_name = models.CharField(max_length=200)
    qr_image = models.ImageField(
        upload_to=payin_qr_image_upload_to,
        max_length=500,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
    )
    account_display_name = models.CharField(max_length=200, blank=True, default='')
    upi_vpa = models.CharField(max_length=120, blank=True, default='')
    bank_details = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    charge_rate = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal('0'),
        help_text='Minimum allowed gateway fee % when this QR is linked on a package.',
    )
    daily_limit_24h = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal('100000'),
        help_text='Max gross amount this QR may collect in a rolling 24h window.',
    )
    max_per_txn = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
        help_text='Optional per-transaction cap for this QR.',
    )

    class Meta:
        db_table = 'pay_in_qr_accounts'
        ordering = ['sort_order', 'display_name']
        indexes = [
            models.Index(fields=['status', 'sort_order']),
        ]

    def __str__(self):
        return self.display_name


class PayInPackageQrLink(BaseModel):
    """Many-to-many: which QR accounts may be used for pay-in on a package."""

    package = models.ForeignKey(
        PayInPackage,
        on_delete=models.CASCADE,
        related_name='package_qr_links',
        db_index=True,
    )
    qr_account = models.ForeignKey(
        PayInQrAccount,
        on_delete=models.CASCADE,
        related_name='package_links',
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(default=False, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    gateway_fee_pct = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
        help_text='Per-QR fee on this package; null uses package.gateway_fee_pct.',
    )

    class Meta:
        db_table = 'pay_in_package_qr_links'
        ordering = ['package_id', 'sort_order', 'id']
        unique_together = [['package', 'qr_account']]
        indexes = [
            models.Index(fields=['package', 'is_active', 'sort_order']),
        ]

    def __str__(self):
        return f'{self.package_id} -> {self.qr_account_id}'


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
        ('PENDING_REVIEW', 'Pending review'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]

    COLLECTION_RAIL_CHOICES = [
        ('gateway', 'Gateway'),
        ('qr', 'QR'),
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
    payment_gateway = models.ForeignKey(
        'admin_panel.PaymentGateway',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='load_money_transactions',
        help_text='Gateway rail used for this pay-in attempt (credentials for verify).',
    )
    collection_rail = models.CharField(
        max_length=16,
        choices=COLLECTION_RAIL_CHOICES,
        default='gateway',
        db_index=True,
    )
    pay_in_qr_account = models.ForeignKey(
        PayInQrAccount,
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
    utr = models.CharField(max_length=64, blank=True, default='', db_index=True)
    payment_date = models.DateField(null=True, blank=True)
    receipt_image = models.ImageField(
        upload_to=payin_receipt_upload_to,
        blank=True,
        null=True,
        max_length=500,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
    )
    submitted_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
        help_text='Amount user declared at QR submit (before admin approval edit).',
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_load_money_transactions',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'load_money'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status', 'created_at']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['collection_rail', 'status', 'created_at']),
            models.Index(fields=['pay_in_qr_account', 'status', 'created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['utr'],
                condition=models.Q(utr__gt=''),
                name='load_money_utr_unique_nonempty',
            ),
        ]

    def __str__(self):
        return f"{self.transaction_id} - {self.user.user_id} - ₹{self.amount}"


class PayInQrApprovalAudit(BaseModel):
    """Append-only audit for manual QR pay-in approve/reject actions."""

    ACTION_CHOICES = [
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('utr_released', 'UTR released'),
    ]

    load_money = models.ForeignKey(
        LoadMoney,
        on_delete=models.CASCADE,
        related_name='qr_approval_audits',
        db_index=True,
    )
    action = models.CharField(max_length=16, choices=ACTION_CHOICES, db_index=True)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='qr_payin_approval_actions',
    )
    submitted_amount = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    approved_amount = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    reject_reason = models.TextField(blank=True, default='')
    internal_note = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'pay_in_qr_approval_audits'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.load_money_id} {self.action}'


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
