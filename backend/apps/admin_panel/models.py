"""
Admin panel models for announcements and gateway management.
"""
import uuid

from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel
from apps.core.utils import decrypt_secret_payload, encrypt_secret_payload


def announcement_image_upload_to(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'bin'
    return f'announcements/{uuid.uuid4().hex}.{ext}'


class Announcement(BaseModel):
    """
    Announcement model for system-wide notifications.
    Supports text-only, image-only, or combined content.
    """
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    title = models.CharField(max_length=200, blank=True, default='')
    message = models.TextField(blank=True, default='')
    image = models.ImageField(
        upload_to=announcement_image_upload_to,
        blank=True,
        null=True,
        max_length=500,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif'])],
    )
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    target_roles = models.JSONField(default=list)  # List of roles; include "All" for every role
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'announcements'
        ordering = ['-created_at']
    
    def __str__(self):
        label = (self.title or '').strip() or '(Image or untitled)'
        return f"{label} - {self.priority}"

    def delete(self, *args, **kwargs):
        if self.image:
            self.image.delete(save=False)
        super().delete(*args, **kwargs)


class PaymentGateway(BaseModel):
    """
    Payment gateway model for load money transactions.
    """
    name = models.CharField(max_length=200)
    charge_rate = models.DecimalField(max_digits=5, decimal_places=2)  # Percentage
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('down', 'Down')], default='active')
    visible_to_roles = models.JSONField(default=list)  # List of roles that can see this gateway
    category = models.CharField(max_length=50, blank=True, null=True)
    api_master = models.ForeignKey(
        'integrations.ApiMaster',
        on_delete=models.SET_NULL,
        related_name='payment_gateways',
        null=True,
        blank=True,
    )
    
    class Meta:
        db_table = 'payment_gateways'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.charge_rate}%"


class PayoutGateway(BaseModel):
    """
    Payout gateway model for payout transactions.
    """
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('down', 'Down')], default='active')
    visible_to_roles = models.JSONField(default=list)  # List of roles that can see this gateway
    
    class Meta:
        db_table = 'payout_gateways'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.status}"


class PayoutSlabConfig(BaseModel):
    """Admin-editable payout slab configuration (add-on charge mode)."""

    name = models.CharField(max_length=80, default='default', unique=True)
    low_max_amount = models.DecimalField(max_digits=18, decimal_places=4, default=24999)
    low_charge = models.DecimalField(max_digits=18, decimal_places=4, default=7)
    high_charge = models.DecimalField(max_digits=18, decimal_places=4, default=15)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'payout_slab_config'
        ordering = ['-is_active', 'id']

    def __str__(self):
        return (
            f"{self.name} | <= {self.low_max_amount}: {self.low_charge} | > {self.low_max_amount}: {self.high_charge}"
        )


class SmtpConfig(BaseModel):
    """Admin-managed SMTP settings for transactional email (e.g. password-reset OTP)."""

    name = models.CharField(max_length=100, default='default', unique=True, db_index=True)
    host = models.CharField(max_length=255, blank=True, default='')
    port = models.PositiveIntegerField(default=587)
    use_tls = models.BooleanField(default=True, help_text='Use STARTTLS (typical for port 587).')
    use_ssl = models.BooleanField(default=False, help_text='Use SSL (typical for port 465).')
    username = models.CharField(max_length=255, blank=True, default='')
    password_encrypted = models.TextField(blank=True, default='')
    from_email = models.EmailField(max_length=254, blank=True, default='')
    enabled = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'smtp_configs'
        ordering = ['-is_active', '-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['is_active'],
                condition=Q(is_active=True, is_deleted=False),
                name='uniq_smtp_active_config',
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.host}:{self.port})"

    def set_password(self, raw_value: str) -> None:
        self.password_encrypted = encrypt_secret_payload({'v': raw_value or ''})

    def get_password(self) -> str:
        return str((decrypt_secret_payload(self.password_encrypted or '') or {}).get('v') or '')
