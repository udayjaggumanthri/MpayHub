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
