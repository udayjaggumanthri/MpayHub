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
        ('simple', 'Simple API'),
    ]
    API_MODE_CHOICES = [
        ('encrypted', 'Encrypted (AES + RSA eskey)'),
        ('simple', 'Simple (plain JSON)'),
    ]
    ONBOARDING_API_STYLE_CHOICES = [
        ('java', 'Java / .NET'),
        ('php', 'PHP'),
    ]
    # Doc 270426 paths under onboarding_base_url (…/fpaepsweb)
    ONBOARDING_CREATE_PATHS = {
        'java': '/api/onboarding/merchant/creation/v2',
        'php': '/api/onboarding/merchant/php/creation/v2',
        'simple': '/api/onboarding/merchant/simple/creation/v2',
    }

    name = models.CharField(max_length=100, unique=True, default='default', db_index=True)
    environment = models.CharField(max_length=10, choices=ENV_CHOICES, default='prod', db_index=True)
    is_active = models.BooleanField(default=False, db_index=True)
    api_mode = models.CharField(
        max_length=12,
        choices=API_MODE_CHOICES,
        default='encrypted',
        db_index=True,
        help_text='encrypted → AES+RSA; simple → plain JSON + secret-key hashes',
    )
    # Which onboarding create API to call when this env row is the active one.
    onboarding_api_style = models.CharField(
        max_length=8,
        choices=ONBOARDING_API_STYLE_CHOICES,
        default='java',
        db_index=True,
        help_text='java → …/merchant/creation/v2 (AES-ECB); php → …/merchant/php/creation/v2 (AES-CBC)',
    )
    debug_mode = models.BooleanField(
        default=False,
        help_text='When on, store full request/response exchange on every Fingpay call',
    )
    egress_ip = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text=(
            'Override for the public egress IP sent as ipAddress. Normally leave blank — '
            'it is auto-detected. Only set it when this host is behind NAT and cannot '
            'see its own public address.'
        ),
    )
    # RD-service finger format asked for at capture time. Readers differ in what
    # they can emit, and a format the device cannot produce reaches UIDAI as
    # "Missing biometric data as specified in Uses", so it is tunable per install.
    FTYPE_CHOICES = [('0', '0 — FMR'), ('1', '1 — FIR'), ('2', '2 — Full image')]
    capture_ftype_aeps = models.CharField(
        max_length=1,
        choices=FTYPE_CHOICES,
        default='2',
        help_text='fType requested for 2FA and AEPS product captures (2 = FMR+FIR; Mantra L1)',
    )
    capture_ftype_ekyc = models.CharField(
        max_length=1,
        choices=FTYPE_CHOICES,
        default='2',
        help_text='fType requested for eKYC captures',
    )

    # Admin-editable relative paths; empty keys fall back to doc defaults
    endpoints_json = models.JSONField(default=dict, blank=True)

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
        return f'AEPS provider {self.name} ({self.environment}/{self.resolved_api_mode})'

    @property
    def resolved_api_mode(self) -> str:
        if (self.environment or '').lower() == 'simple':
            return 'simple'
        mode = (self.api_mode or 'encrypted').lower()
        return mode if mode in ('encrypted', 'simple') else 'encrypted'

    @property
    def resolved_onboarding_api_style(self) -> str:
        if self.resolved_api_mode == 'simple':
            return 'simple'
        style = (self.onboarding_api_style or 'java').lower()
        return style if style in ('java', 'php') else 'java'

    def resolved_endpoints(self) -> dict:
        from apps.integrations.fingpay.endpoints import merge_endpoints

        return merge_endpoints(
            self.endpoints_json,
            environment=self.environment,
            onboarding_api_style=self.onboarding_api_style or 'php',
        )

    def endpoint_path(self, key: str, default: str = '') -> str:
        return str(self.resolved_endpoints().get(key) or default or '')

    def onboarding_create_path(self) -> str:
        style = self.resolved_onboarding_api_style
        if style == 'simple':
            return self.endpoint_path('onboarding_create_simple', self.ONBOARDING_CREATE_PATHS['simple'])
        if style == 'php':
            return self.endpoint_path('onboarding_create_php', self.ONBOARDING_CREATE_PATHS['php'])
        return self.endpoint_path('onboarding_create_java', self.ONBOARDING_CREATE_PATHS['java'])

    def onboarding_create_url(self) -> str:
        base = (self.onboarding_base_url or '').rstrip('/')
        path = self.onboarding_create_path()
        return f'{base}{path}' if base else path

    def onboarding_aes_mode(self) -> str:
        # PHP sample: AES-128-CBC; Java/.NET sample: AES-128-ECB
        return 'cbc' if self.resolved_onboarding_api_style == 'php' else 'ecb'

    def resolved_egress_ip(self) -> str:
        """Detected outbound address, with the stored value as a NAT override."""
        from apps.integrations.fingpay.netinfo import resolve_egress_ip

        return resolve_egress_ip(
            self.egress_ip or '',
            url=self.onboarding_base_url or self.aeps_base_url or '',
        )


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

    device_imei = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='Phone/tablet IMEI sent as Fingpay deviceIMEI header',
    )
    scanner_serial = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='Mantra fingerprint scanner serial (local RD + optional matmSerialNumber)',
    )
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
    # Scrubbed summaries only — never PID / full Aadhaar (always populated)
    request_summary = models.JSONField(default=dict, blank=True)
    response_summary = models.JSONField(default=dict, blank=True)
    # Full exchange when provider debug_mode is on (for Tapits sharing)
    debug_enabled = models.BooleanField(default=False, db_index=True)
    request_headers = models.JSONField(default=dict, blank=True)
    request_body = models.JSONField(default=dict, blank=True)
    response_body = models.JSONField(default=dict, blank=True)
    exchange_pack = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'aeps_api_audit_logs'
        ordering = ['-created_at']
