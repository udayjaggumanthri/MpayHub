"""
SMS provider config, per-event templates, and delivery audit logs.
"""
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel
from apps.core.utils import decrypt_secret_payload, encrypt_secret_payload


class SmsProviderConfig(BaseModel):
    """Admin-managed MSG91 (or console) settings for transactional SMS."""

    PROVIDER_CHOICES = [
        ('msg91', 'MSG91'),
        ('console', 'Console (dev log only)'),
    ]

    name = models.CharField(max_length=100, default='default', unique=True, db_index=True)
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES, default='msg91')
    auth_key_encrypted = models.TextField(blank=True, default='')
    sender_id = models.CharField(max_length=20, blank=True, default='')
    enabled = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=False, db_index=True)
    api_base_url = models.CharField(
        max_length=255,
        blank=True,
        default='https://control.msg91.com',
        help_text='MSG91 API host (no trailing slash).',
    )
    route = models.CharField(max_length=32, blank=True, default='')
    country_code = models.CharField(max_length=4, default='91')
    last_test_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=32, blank=True, default='')
    last_test_error = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'sms_provider_configs'
        ordering = ['-is_active', '-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['is_active'],
                condition=Q(is_active=True, is_deleted=False),
                name='uniq_sms_active_config',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.provider})'

    def set_auth_key(self, raw_value: str) -> None:
        self.auth_key_encrypted = encrypt_secret_payload({'v': raw_value or ''})

    def get_auth_key(self) -> str:
        return str((decrypt_secret_payload(self.auth_key_encrypted or '') or {}).get('v') or '')


class SmsNotificationTemplate(BaseModel):
    """Per-event DLT template mapping; seeded from catalog, updated via admin API."""

    event_key = models.CharField(max_length=80, unique=True, db_index=True)
    module = models.CharField(max_length=40, db_index=True)
    label = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    is_enabled = models.BooleanField(default=False, db_index=True)
    template_id = models.CharField(max_length=64, blank=True, default='')
    variable_schema = models.JSONField(default=list, blank=True)
    sample_variables = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'sms_notification_templates'
        ordering = ['module', 'event_key']

    def __str__(self):
        return f'{self.event_key} ({self.module})'


class SmsDeliveryLog(BaseModel):
    """Audit trail for SMS dispatch attempts."""

    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]

    event_key = models.CharField(max_length=80, db_index=True)
    idempotency_key = models.CharField(max_length=200, unique=True, db_index=True)
    user = models.ForeignKey(
        'authentication.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='sms_delivery_logs',
    )
    phone_masked = models.CharField(max_length=20, blank=True, default='')
    template_id = models.CharField(max_length=64, blank=True, default='')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, db_index=True)
    skip_reason = models.CharField(max_length=64, blank=True, default='')
    provider_message_id = models.CharField(max_length=128, blank=True, default='')
    error_message = models.TextField(blank=True, default='')
    context_json = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'sms_delivery_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.event_key} {self.status} ({self.idempotency_key[:40]})'
