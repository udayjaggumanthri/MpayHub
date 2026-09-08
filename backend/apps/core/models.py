"""
Core abstract base models for the mPayhub platform.
"""
import uuid

from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


def platform_logo_upload_to(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'bin'
    return f'branding/logo/{uuid.uuid4().hex}.{ext}'


class TimestampedModel(models.Model):
    """Abstract model with created_at and updated_at timestamps."""
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        ordering = ['-created_at']


class SoftDeleteModel(models.Model):
    """Abstract model with soft delete functionality."""
    
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    
    def soft_delete(self):
        """Mark the object as deleted without actually deleting it."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])
    
    def restore(self):
        """Restore a soft-deleted object."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])
    
    class Meta:
        abstract = True


class BaseModel(TimestampedModel, SoftDeleteModel):
    """Combined base model with timestamps and soft delete."""
    
    class Meta:
        abstract = True


class SystemMaintenanceConfig(models.Model):
    """
    Singleton platform maintenance flags (pk=1).
    Blocks new transaction activity per module for all users when disabled.
    """

    SINGLETON_PK = 1

    pay_in_enabled = models.BooleanField(default=True, db_index=True)
    payout_enabled = models.BooleanField(default=True, db_index=True)
    bbps_enabled = models.BooleanField(default=True, db_index=True)
    aeps_enabled = models.BooleanField(default=False, db_index=True)
    pay_in_message = models.TextField(blank=True, default='')
    payout_message = models.TextField(blank=True, default='')
    bbps_message = models.TextField(blank=True, default='')
    aeps_message = models.TextField(blank=True, default='')
    reason_internal = models.TextField(blank=True, default='')
    updated_by = models.ForeignKey(
        'authentication.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='maintenance_config_updates',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_maintenance_config'
        verbose_name = 'System maintenance config'
        verbose_name_plural = 'System maintenance config'

    def __str__(self):
        return 'System maintenance config'

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)


class SystemMaintenanceAuditLog(TimestampedModel):
    """Append-only audit trail for maintenance changes."""

    MODULE_CHOICES = [
        ('pay_in', 'Pay-in'),
        ('payout', 'Payout'),
        ('bbps', 'BBPS'),
        ('aeps', 'AEPS'),
        ('all', 'All modules'),
    ]

    module = models.CharField(max_length=20, choices=MODULE_CHOICES, db_index=True)
    enabled = models.BooleanField()
    user_message = models.TextField(blank=True, default='')
    reason_internal = models.TextField(blank=True, default='')
    changed_by = models.ForeignKey(
        'authentication.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='maintenance_audit_entries',
    )

    class Meta:
        db_table = 'system_maintenance_audit_logs'
        ordering = ['-created_at']

    def __str__(self):
        state = 'enabled' if self.enabled else 'disabled'
        return f'{self.module} {state} at {self.created_at}'


class PlatformAppearanceConfig(models.Model):
    """
    Singleton platform branding and theme settings (pk=1).
    """

    SINGLETON_PK = 1

    THEME_LIGHT = 'light'
    THEME_DARK = 'dark'
    THEME_CHOICES = [
        (THEME_LIGHT, 'Light'),
        (THEME_DARK, 'Dark'),
    ]

    site_title = models.CharField(max_length=120, default='mPayHub')
    logo = models.ImageField(
        upload_to=platform_logo_upload_to,
        blank=True,
        null=True,
        max_length=500,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif'])],
    )
    login_welcome_heading = models.CharField(max_length=200, default='WELCOME TO')
    login_tagline = models.CharField(max_length=300, default='Driven by trust, Built for Scale')
    login_footer_note = models.TextField(blank=True, default='')
    login_footer_privacy_url = models.URLField(blank=True, default='')
    login_footer_terms_url = models.URLField(blank=True, default='')
    login_footer_refund_url = models.URLField(blank=True, default='')
    default_theme = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default=THEME_LIGHT,
        db_index=True,
    )
    user_theme_toggle_enabled = models.BooleanField(default=False, db_index=True)
    updated_by = models.ForeignKey(
        'authentication.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='appearance_config_updates',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'platform_appearance_config'
        verbose_name = 'Platform appearance config'
        verbose_name_plural = 'Platform appearance config'

    def __str__(self):
        return 'Platform appearance config'

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from apps.core.media_files import discard_stored_file

        if self.logo:
            discard_stored_file(self.logo)
        super().delete(*args, **kwargs)


class PortalAccessConfig(models.Model):
    """
    Singleton portal login gate (pk=1).
    When test_usage_mode_enabled is True, only Super Admin and is_test_user accounts may log in.
    """

    SINGLETON_PK = 1

    test_usage_mode_enabled = models.BooleanField(default=False, db_index=True)
    test_usage_title = models.CharField(max_length=200, blank=True, default='Test usage mode')
    test_usage_message = models.TextField(
        blank=True,
        default='The portal is currently in test usage mode. Contact your administrator.',
    )
    updated_by = models.ForeignKey(
        'authentication.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='portal_access_config_updates',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portal_access_config'
        verbose_name = 'Portal access config'
        verbose_name_plural = 'Portal access config'

    def __str__(self):
        return 'Portal access config'

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)


class AppModule(models.Model):
    """Named portal module used for role × module permission matrix."""

    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    group = models.CharField(max_length=64, blank=True, default='')
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'app_modules'
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f'{self.code} ({self.name})'


class RoleModulePermission(models.Model):
    """Per-role enable flag for an AppModule."""

    role = models.CharField(max_length=20, db_index=True)
    module_code = models.CharField(max_length=64, db_index=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'role_module_permissions'
        unique_together = [('role', 'module_code')]
        ordering = ['role', 'module_code']

    def __str__(self):
        state = 'on' if self.enabled else 'off'
        return f'{self.role} / {self.module_code} = {state}'
