"""
Admin panel models for announcements and gateway management.
"""
from django.db import models
from apps.core.models import BaseModel
from apps.authentication.models import User


class Announcement(BaseModel):
    """
    Announcement model for system-wide notifications.
    """
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    target_roles = models.JSONField(default=list)  # List of roles this announcement targets
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'announcements'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.priority}"


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
