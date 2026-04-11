from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel


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
