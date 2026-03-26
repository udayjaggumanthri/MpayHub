"""
Bank account models for the mPayhub platform.
"""
from django.db import models
from apps.core.models import BaseModel
from apps.authentication.models import User
from apps.contacts.models import Contact


class BankAccount(BaseModel):
    """
    Bank account model.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bank_accounts',
        db_index=True
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        related_name='bank_accounts',
        null=True,
        blank=True
    )
    account_number = models.CharField(max_length=20, db_index=True)
    ifsc = models.CharField(max_length=11)
    bank_name = models.CharField(max_length=200)
    account_holder_name = models.CharField(max_length=200)
    beneficiary_name = models.CharField(max_length=200, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'bank_accounts'
        unique_together = [['user', 'account_number', 'ifsc']]
        indexes = [
            models.Index(fields=['user', 'account_number']),
        ]
    
    def __str__(self):
        return f"{self.account_holder_name} - {self.account_number[-4:]}"
