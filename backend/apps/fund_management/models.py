"""
Fund management models for Load Money and Payout.
"""
from django.db import models
from decimal import Decimal
from apps.core.models import BaseModel
from apps.authentication.models import User
from apps.bank_accounts.models import BankAccount


class LoadMoney(BaseModel):
    """
    Load Money transaction model.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='load_money_transactions',
        db_index=True
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    gateway = models.CharField(max_length=100)
    charge = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_credit = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    gateway_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'load_money'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status', 'created_at']),
            models.Index(fields=['transaction_id']),
        ]
    
    def __str__(self):
        return f"{self.transaction_id} - {self.user.user_id} - ₹{self.amount}"


class Payout(BaseModel):
    """
    Payout transaction model.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payout_transactions',
        db_index=True
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='payouts'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    charge = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_deducted = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    gateway_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'payouts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status', 'created_at']),
            models.Index(fields=['transaction_id']),
        ]
    
    def __str__(self):
        return f"{self.transaction_id} - {self.user.user_id} - ₹{self.amount}"
