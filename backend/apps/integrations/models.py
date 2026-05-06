from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel
from apps.core.utils import decrypt_secret_payload, encrypt_secret_payload


class ApiMaster(BaseModel):
    """Central provider registry with encrypted credentials."""

    PROVIDER_TYPE_CHOICES = [
        ('kyc', 'KYC'),
        ('payments', 'Payments'),
        ('banking', 'Banking'),
        ('utility', 'Utility'),
        ('other', 'Other'),
    ]
    AUTH_TYPE_CHOICES = [
        ('api_key', 'API Key'),
        ('bearer', 'Bearer'),
        ('basic', 'Basic'),
        ('oauth2', 'OAuth2'),
        ('custom', 'Custom'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('down', 'Down'),
        ('sandbox', 'Sandbox'),
    ]

    provider_code = models.SlugField(max_length=80, unique=True, db_index=True)
    provider_name = models.CharField(max_length=200)
    provider_type = models.CharField(max_length=20, choices=PROVIDER_TYPE_CHOICES, db_index=True)
    base_url = models.URLField(max_length=500, blank=True)
    auth_type = models.CharField(max_length=20, choices=AUTH_TYPE_CHOICES, default='api_key')
    config_json = models.JSONField(default=dict, blank=True)
    secrets_encrypted = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive', db_index=True)
    priority = models.PositiveIntegerField(default=0, db_index=True)
    is_default = models.BooleanField(default=False, db_index=True)
    supports_webhook = models.BooleanField(default=False)
    webhook_path = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'api_masters'
        ordering = ['provider_type', '-is_default', 'priority', 'provider_name']
        constraints = [
            models.UniqueConstraint(
                fields=['provider_type'],
                condition=Q(is_default=True, is_deleted=False),
                name='uniq_active_default_per_provider_type',
            ),
        ]

    def __str__(self):
        return f"{self.provider_name} ({self.provider_code})"


class BillAvenueConfig(BaseModel):
    """Environment-specific BillAvenue configuration (admin-managed)."""

    MODE_CHOICES = [('mock', 'Mock'), ('uat', 'UAT'), ('prod', 'Production')]
    API_FORMAT_CHOICES = [('json', 'JSON'), ('xml', 'XML')]
    KEY_DERIVATION_CHOICES = [('rawhex', 'Raw hex (AES key bytes)'), ('md5', 'MD5 (legacy PHP samples)')]
    ENC_REQUEST_ENCODING_CHOICES = [('base64', 'Base64'), ('hex', 'Hex')]

    name = models.CharField(max_length=100, unique=True, db_index=True)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='mock', db_index=True)
    api_format = models.CharField(max_length=10, choices=API_FORMAT_CHOICES, default='json')
    crypto_key_derivation = models.CharField(max_length=20, choices=KEY_DERIVATION_CHOICES, default='md5')
    enc_request_encoding = models.CharField(max_length=20, choices=ENC_REQUEST_ENCODING_CHOICES, default='hex')
    allow_variant_fallback = models.BooleanField(default=True)
    allow_txn_status_path_fallback = models.BooleanField(default=True)
    base_url = models.URLField(max_length=500, blank=True, default='')
    access_code = models.CharField(max_length=150, blank=True, default='')
    institute_id = models.CharField(max_length=50, blank=True, default='')
    request_version = models.CharField(max_length=10, blank=True, default='1.0')
    working_key_encrypted = models.TextField(blank=True, default='')
    iv_encrypted = models.TextField(blank=True, default='')
    callback_secret_encrypted = models.TextField(blank=True, default='')
    connect_timeout_seconds = models.PositiveIntegerField(default=30)
    read_timeout_seconds = models.PositiveIntegerField(default=60)
    max_retries = models.PositiveIntegerField(default=2)
    mdm_refresh_hours = models.PositiveIntegerField(default=24)
    mdm_max_calls_per_day = models.PositiveIntegerField(default=15)
    push_callback_url = models.URLField(max_length=500, blank=True, default='')
    enabled = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=False, db_index=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    activated_by = models.ForeignKey(
        'authentication.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='billavenue_activated_configs',
    )

    BBPS_WALLET_CHARGE_MODE_CHOICES = [
        ('FLAT', 'Flat amount'),
        ('PERCENT', 'Percent of bill amount'),
    ]
    bbps_wallet_service_charge_mode = models.CharField(
        max_length=10,
        choices=BBPS_WALLET_CHARGE_MODE_CHOICES,
        default='FLAT',
        help_text='How BBPS wallet service charge is computed for quote and payment.',
    )
    bbps_wallet_service_charge_flat = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=5,
        help_text='Flat charge (INR) when mode is FLAT.',
    )
    bbps_wallet_service_charge_percent = models.DecimalField(
        max_digits=9,
        decimal_places=4,
        default=0,
        help_text='Percent of bill amount when mode is PERCENT (e.g. 1.25 = 1.25%).',
    )

    class Meta:
        db_table = 'billavenue_configs'
        ordering = ['-is_active', '-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['is_active'],
                condition=Q(is_active=True, is_deleted=False),
                name='uniq_billavenue_active_config',
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.mode})"

    def set_working_key(self, raw_value: str) -> None:
        self.working_key_encrypted = encrypt_secret_payload({'v': raw_value or ''})

    def get_working_key(self) -> str:
        return str((decrypt_secret_payload(self.working_key_encrypted or '') or {}).get('v') or '')

    def set_iv(self, raw_value: str) -> None:
        self.iv_encrypted = encrypt_secret_payload({'v': raw_value or ''})

    def get_iv(self) -> str:
        return str((decrypt_secret_payload(self.iv_encrypted or '') or {}).get('v') or '')

    def set_callback_secret(self, raw_value: str) -> None:
        self.callback_secret_encrypted = encrypt_secret_payload({'v': raw_value or ''})

    def get_callback_secret(self) -> str:
        return str((decrypt_secret_payload(self.callback_secret_encrypted or '') or {}).get('v') or '')


class BillAvenueAgentProfile(BaseModel):
    """Agent/channel defaults controlled by Admin for BillAvenue requests."""

    CHANNEL_CHOICES = [
        ('AGT', 'AGT'),
        ('INT', 'INT'),
        ('MOB', 'MOB'),
        ('INTB', 'INTB'),
        ('MOBB', 'MOBB'),
        ('POS', 'POS'),
        ('ATM', 'ATM'),
        ('BNKBRNCH', 'BNKBRNCH'),
        ('BSC', 'BSC'),
        ('KIOSK', 'KIOSK'),
        ('MPOS', 'MPOS'),
    ]

    config = models.ForeignKey(
        BillAvenueConfig, on_delete=models.CASCADE, related_name='agent_profiles'
    )
    name = models.CharField(max_length=100, default='default')
    agent_id = models.CharField(max_length=40, db_index=True)
    init_channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='AGT')
    require_ip = models.BooleanField(default=True)
    require_mac = models.BooleanField(default=False)
    require_imei = models.BooleanField(default=False)
    require_os = models.BooleanField(default=False)
    require_app = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'billavenue_agent_profiles'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['config', 'name'],
                condition=Q(is_deleted=False),
                name='uniq_billavenue_agent_profile_name_per_config',
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.agent_id}"


class BillAvenueModeChannelPolicy(BaseModel):
    """Allowed/blocked payment mode/channel policy with optional biller/category overrides."""

    ACTION_CHOICES = [('allow', 'Allow'), ('deny', 'Deny')]

    config = models.ForeignKey(
        BillAvenueConfig, on_delete=models.CASCADE, related_name='mode_channel_policies'
    )
    payment_mode = models.CharField(max_length=50, db_index=True)
    payment_channel = models.CharField(max_length=20, db_index=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, default='allow')
    biller_id = models.CharField(max_length=20, blank=True, default='')
    biller_category = models.CharField(max_length=100, blank=True, default='')
    enabled = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'billavenue_mode_channel_policies'
        ordering = ['payment_mode', 'payment_channel']
        indexes = [
            models.Index(fields=['payment_mode', 'payment_channel']),
            models.Index(fields=['biller_id', 'biller_category']),
        ]

    def __str__(self):
        suffix = f" [{self.biller_id or self.biller_category or 'global'}]"
        return f"{self.action.upper()} {self.payment_mode}/{self.payment_channel}{suffix}"
