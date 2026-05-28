"""
Core abstract base models for the mPayhub platform.
"""
from django.db import models
from django.utils import timezone


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
    pay_in_message = models.TextField(blank=True, default='')
    payout_message = models.TextField(blank=True, default='')
    bbps_message = models.TextField(blank=True, default='')
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
