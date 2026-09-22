"""
Uber CMS domain models — isolated ledger/reports (no shared Wallet wallet_type).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel, TimestampedModel


class CmsProviderConfig(BaseModel):
    """Singleton-style Fingpay Uber CMS super-merchant credentials (admin-managed)."""

    ENV_CHOICES = [
        ('uat', 'UAT'),
        ('prod', 'Production'),
    ]

    name = models.CharField(max_length=100, unique=True, default='default', db_index=True)
    environment = models.CharField(max_length=10, choices=ENV_CHOICES, default='uat', db_index=True)
    is_active = models.BooleanField(default=False, db_index=True)
    login_type = models.CharField(max_length=8, default='2')
    super_merchant_id = models.CharField(max_length=64, blank=True, default='')
    cms_base_url = models.URLField(max_length=500, blank=True, default='')
    login_path = models.CharField(max_length=200, default='/UberCMSBC/#/login')
    # Encrypted JSON: super_merchant_skey, secret_key
    secrets_encrypted = models.TextField(blank=True, default='')
    # Hash concatenation template; default matches doc sample payload+secretKey
    hash_template = models.CharField(max_length=64, default='{payload}{secret_key}')
    allowed_inbound_ips = models.JSONField(default=list, blank=True)
    debug_mode = models.BooleanField(
        default=False,
        help_text='When on, store full request/response bodies on inbound CMS webhooks',
    )
    hold_ttl_hours = models.PositiveIntegerField(
        default=24,
        help_text='Hours before an initiated hold is auto-released as expired',
    )
    notes = models.TextField(blank=True, default='')
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cms_provider_updates',
    )

    class Meta:
        db_table = 'cms_provider_configs'
        ordering = ['-is_active', 'name']

    def __str__(self):
        return f'CMS provider {self.name} ({self.environment})'


class CmsEntitlement(BaseModel):
    """Admin-only per-user CMS access. No hierarchy inheritance."""

    SOURCE_CHOICES = [
        ('manual', 'Manual'),
        ('access_request', 'Access request'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cms_entitlement',
    )
    enabled = models.BooleanField(default=True, db_index=True)
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default='manual')
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cms_entitlements_assigned',
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    disabled_reason = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        db_table = 'cms_entitlements'
        ordering = ['-updated_at']

    def __str__(self):
        state = 'on' if self.enabled else 'off'
        return f'CMS entitlement {self.user_id} ({state})'


class CmsAgentProfile(BaseModel):
    """BC agent mapping for an entitled mPayHub user (independent of AEPS)."""

    STATUS_CHOICES = [
        ('inactive', 'Inactive'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cms_agent',
    )
    bc_login_id = models.CharField(max_length=64, unique=True, db_index=True)
    merchant_pin_encrypted = models.TextField(blank=True, default='')
    mobile_number = models.CharField(max_length=15, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive', db_index=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'cms_agent_profiles'
        ordering = ['-updated_at']

    def __str__(self):
        return f'CMS agent {self.bc_login_id} ({self.status})'


class CmsWallet(BaseModel):
    """Dedicated CMS BC ledger balance (not a shared Wallet wallet_type)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cms_wallet',
    )
    balance = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    held_balance = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    class Meta:
        db_table = 'cms_wallets'

    def __str__(self):
        return f'CMS wallet {self.user_id} bal={self.balance} held={self.held_balance}'

    @property
    def available(self):
        return self.balance - self.held_balance


class CmsWalletEntry(BaseModel):
    ENTRY_TYPE_CHOICES = [
        ('fund', 'Fund from main'),
        ('unfund', 'Return to main'),
        ('hold', 'Hold'),
        ('settle', 'Settle hold'),
        ('release', 'Release hold'),
        ('adjustment', 'Adjustment'),
    ]

    wallet = models.ForeignKey(CmsWallet, on_delete=models.CASCADE, related_name='entries')
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=4)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=4)
    reference = models.CharField(max_length=128, blank=True, default='', db_index=True)
    transaction = models.ForeignKey(
        'CmsTransaction',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='wallet_entries',
    )
    description = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        db_table = 'cms_wallet_entries'
        ordering = ['-created_at']


class CmsTransaction(BaseModel):
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cms_transactions',
    )
    agent = models.ForeignKey(
        CmsAgentProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='transactions',
    )
    merchant_transaction_id = models.CharField(max_length=64, unique=True, db_index=True)
    fp_transaction_id = models.CharField(max_length=128, unique=True, db_index=True)
    type_of_transaction = models.CharField(max_length=16, default='CDC', db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated', db_index=True)
    bc_login_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
    agent_login_id = models.CharField(max_length=64, blank=True, default='')
    drop_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    error_message = models.CharField(max_length=500, blank=True, default='')
    remarks = models.CharField(max_length=500, blank=True, default='')
    provider_meta = models.JSONField(default=dict, blank=True)
    initiated_at = models.DateTimeField(null=True, blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'cms_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'{self.merchant_transaction_id} {self.status}'


class CmsLaunchSession(BaseModel):
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('opened', 'Opened'),
        ('consumed', 'Consumed'),
        ('expired', 'Expired'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cms_launch_sessions',
    )
    agent = models.ForeignKey(
        CmsAgentProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='launch_sessions',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created', db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'cms_launch_sessions'
        ordering = ['-created_at']


class CmsApiAuditLog(TimestampedModel):
    endpoint = models.CharField(max_length=255, db_index=True)
    method = models.CharField(max_length=10, default='POST')
    merchant_transaction_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
    fp_transaction_id = models.CharField(max_length=128, blank=True, default='', db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cms_api_audits',
    )
    http_status = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.CharField(max_length=500, blank=True, default='')
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    request_summary = models.JSONField(default=dict, blank=True)
    response_summary = models.JSONField(default=dict, blank=True)
    debug_enabled = models.BooleanField(default=False, db_index=True)
    request_headers = models.JSONField(default=dict, blank=True)
    request_body = models.JSONField(default=dict, blank=True)
    response_body = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'cms_api_audit_logs'
        ordering = ['-created_at']
