"""
BBPS (Bharat Bill Payment System) models.
"""
from django.db import models
from decimal import Decimal
from apps.core.models import BaseModel
from apps.authentication.models import User
from django.conf import settings


class Biller(BaseModel):
    """
    Biller model for BBPS.
    """
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, db_index=True)
    biller_id = models.CharField(max_length=100, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'biller'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.category}"


class Bill(BaseModel):
    """
    Bill model for storing bill details.
    """
    biller = models.ForeignKey(Biller, on_delete=models.CASCADE, related_name='bills')
    customer_details = models.JSONField(default=dict)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    
    class Meta:
        db_table = 'bills'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Bill - {self.biller.name} - ₹{self.amount}"


class BillPayment(BaseModel):
    """
    Bill payment transaction model.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bill_payments',
        db_index=True
    )
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    biller = models.CharField(max_length=200)
    biller_id = models.CharField(max_length=100, blank=True, null=True)
    bill_type = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    charge = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal(str(settings.BBPS_SERVICE_CHARGE)))
    total_deducted = models.DecimalField(max_digits=18, decimal_places=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    service_id = models.CharField(max_length=100, unique=True, db_index=True)
    request_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    failure_reason = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'bill_payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status', 'created_at']),
            models.Index(fields=['service_id']),
        ]
    
    def __str__(self):
        return f"{self.service_id} - {self.user.user_id} - ₹{self.amount}"
