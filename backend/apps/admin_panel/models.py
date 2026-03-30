"""
Admin panel models for announcements and gateway management.
"""
import uuid

from django.core.validators import FileExtensionValidator
from django.db import models
from apps.core.models import BaseModel


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
