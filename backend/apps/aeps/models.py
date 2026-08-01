"""
AEPS domain models — self-contained ledger/reports (no shared Transaction/Passbook in v1).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel, TimestampedModel


class AepsProviderConfig(BaseModel):
    """Singleton-style Fingpay super-merchant credentials (admin-managed)."""

    ENV_CHOICES = [
        ('uat', 'UAT'),
        ('prod', 'Production'),
    ]

    name = models.CharField(max_length=100, unique=True, default='default', db_index=True)
    environment = models.CharField(max_length=10, choices=ENV_CHOICES, default='uat', db_index=True)
    is_active = models.BooleanField(default=False, db_index=True)

    super_merchant_id = models.CharField(max_length=64, blank=True, default='')
    super_merchant_login_id = models.CharField(max_length=128, blank=True, default='')
    # Encrypted JSON: password, secret_key, rsa_public_key_pem, optional extras
    secrets_encrypted = models.TextField(blank=True, default='')

    onboarding_base_url = models.URLField(max_length=500, blank=True, default='')
    ekyc_base_url = models.URLField(max_length=500, blank=True, default='')
    aeps_base_url = models.URLField(max_length=500, blank=True, default='')
    recon_base_url = models.URLField(max_length=500, blank=True, default='')

    bank_list_url = models.URLField(max_length=500, blank=True, default='')
    aadhaar_pay_bank_list_url = models.URLField(max_length=500, blank=True, default='')

    request_timeout_seconds = models.PositiveIntegerField(default=180)
    notes = models.TextField(blank=True, default='')
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='aeps_provider_updates',
    )

    class Meta:
        db_table = 'aeps_provider_configs'
        ordering = ['-is_active', 'name']

    def __str__(self):
        return f'AEPS provider {self.name} ({self.environment})'


class AepsEntitlement(BaseModel):
    """Admin-only per-user AEPS access. No hierarchy inheritance."""

    SOURCE_CHOICES = [
        ('on_create', 'On user create'),
        ('manual', 'Manual'),
        ('access_request', 'Access request'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='aeps_entitlement',
    )
    enabled = models.BooleanField(default=True, db_index=True)
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default='manual')
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='aeps_entitlements_assigned',
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    disabled_reason = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        db_table = 'aeps_entitlements'
        ordering = ['-updated_at']

    def __str__(self):
        state = 'on' if self.enabled else 'off'
        return f'AEPS entitlement {self.user_id} ({state})'


class AepsAccessRequest(BaseModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='aeps_access_requests',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    reason = models.TextField(blank=True, default='')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='aeps_access_reviews',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'aeps_access_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]


class AepsMerchantProfile(BaseModel):
    """Fingpay merchant mapping for an entitled mPayHub user."""

    STAGE_CHOICES = [
        ('not_started', 'Not started'),
        ('onboarding_draft', 'Onboarding draft'),
        ('onboarding_submitted', 'Onboarding submitted'),
        ('ekyc_pending', 'eKYC pending'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('rejected', 'Rejected'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='aeps_merchant_profile',
    )
    merchant_login_id = models.CharField(max_length=64, unique=True, db_index=True)
    merchant_pin_encrypted = models.TextField(blank=True, default='')
    stage = models.CharField(max_length=32, choices=STAGE_CHOICES, default='not_started', db_index=True)

    # Onboarding payload snapshot (no full Aadhaar / PID)
    onboarding_payload = models.JSONField(default=dict, blank=True)
    fingpay_onboarding_ref = models.CharField(max_length=128, blank=True, default='')
    fingpay_ekyc_ref = models.CharField(max_length=128, blank=True, default='')
    ekyc_primary_key_id = models.CharField(max_length=64, blank=True, default='')
    ekyc_encode_fp_txn_id = models.CharField(max_length=128, blank=True, default='')
    masked_aadhaar = models.CharField(max_length=20, blank=True, default='')

    device_imei = models.CharField(max_length=64, blank=True, default='', help_text='Mantra scanner serial')
    device_ready = models.BooleanField(default=False)
    last_2fa_at = models.DateTimeField(null=True, blank=True)
    last_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    last_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    activated_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'aeps_merchant_profiles'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.merchant_login_id} ({self.stage})'


class AepsDaily2FA(TimestampedModel):
    merchant = models.ForeignKey(
        AepsMerchantProfile,
        on_delete=models.CASCADE,
        related_name='daily_2fa',
    )
    for_date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, default='pending', db_index=True)
    fingpay_ref = models.CharField(max_length=128, blank=True, default='')
    response_code = models.CharField(max_length=16, blank=True, default='')
    message = models.CharField(max_length=500, blank=True, default='')
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'aeps_daily_2fa'
        unique_together = [('merchant', 'for_date')]
        ordering = ['-for_date']


class AepsTransaction(BaseModel):
    """Sole AEPS transaction store (not shared ledger)."""

    PRODUCT_CHOICES = [
        ('CW', 'Cash Withdrawal'),
        ('BE', 'Balance Enquiry'),
        ('MS', 'Mini Statement'),
        ('AP', 'Aadhaar Pay'),
        ('CD', 'Cash Deposit'),
        ('EKY', 'eKYC'),
        ('2FA', 'Daily 2FA'),
        ('ONB', 'Onboarding'),
    ]
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
        ('reconciled', 'Reconciled'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='aeps_transactions',
    )
    merchant = models.ForeignKey(
        AepsMerchantProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='transactions',
    )
    merchant_tran_id = models.CharField(max_length=64, unique=True, db_index=True)
    product = models.CharField(max_length=8, choices=PRODUCT_CHOICES, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated', db_index=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    bank_iin = models.CharField(max_length=20, blank=True, default='')
    bank_name = models.CharField(max_length=120, blank=True, default='')
    masked_aadhaar = models.CharField(max_length=20, blank=True, default='')
    customer_mobile = models.CharField(max_length=15, blank=True, default='')

    fp_transaction_id = models.CharField(max_length=128, blank=True, default='', db_index=True)
    bank_rrn = models.CharField(max_length=64, blank=True, default='', db_index=True)
    response_code = models.CharField(max_length=16, blank=True, default='')
    response_message = models.CharField(max_length=500, blank=True, default='')
    balance_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    mini_statement = models.JSONField(default=list, blank=True)

    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    device_imei = models.CharField(max_length=64, blank=True, default='')
    client_ip = models.GenericIPAddressField(null=True, blank=True)

    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    provider_meta = models.JSONField(default=dict, blank=True)  # redacted only

    class Meta:
        db_table = 'aeps_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['product', 'status', '-created_at']),
        ]

    def __str__(self):
        return f'{self.merchant_tran_id} {self.product} {self.status}'


class AepsBankIinCache(TimestampedModel):
    list_type = models.CharField(max_length=20, default='aeps', db_index=True)  # aeps | aadhaar_pay
    iin = models.CharField(max_length=20, db_index=True)
    bank_name = models.CharField(max_length=200)
    raw = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'aeps_bank_iin_cache'
        unique_together = [('list_type', 'iin')]
        ordering = ['bank_name']


class AepsReconBatch(TimestampedModel):
    txn_date = models.CharField(max_length=64, blank=True, default='')
    request_hash = models.CharField(max_length=128, blank=True, default='')
    item_count = models.PositiveIntegerField(default=0)
    raw_request = models.JSONField(default=dict, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'aeps_recon_batches'
        ordering = ['-created_at']


class AepsReconItem(TimestampedModel):
    batch = models.ForeignKey(AepsReconBatch, on_delete=models.CASCADE, related_name='items')
    merchant_tran_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
    fp_transaction_id = models.CharField(max_length=128, blank=True, default='')
    our_status = models.CharField(max_length=32, blank=True, default='')
    reply_code = models.CharField(max_length=32, blank=True, default='')  # 00 or Failed
    matched_transaction = models.ForeignKey(
        AepsTransaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='recon_items',
    )
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'aeps_recon_items'
        ordering = ['id']


class AepsApiAuditLog(TimestampedModel):
    endpoint = models.CharField(max_length=255, db_index=True)
    method = models.CharField(max_length=10, default='POST')
    merchant_tran_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='aeps_api_audits',
    )
    http_status = models.PositiveIntegerField(null=True, blank=True)
    provider_status_code = models.CharField(max_length=32, blank=True, default='')
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.CharField(max_length=500, blank=True, default='')
    # Scrubbed summaries only — never PID / full Aadhaar
    request_summary = models.JSONField(default=dict, blank=True)
    response_summary = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'aeps_api_audit_logs'
        ordering = ['-created_at']
