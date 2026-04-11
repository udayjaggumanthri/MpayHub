"""
Contact models for the mPayhub platform.
"""
from django.db import models
from apps.core.models import BaseModel
from apps.authentication.models import User


class Contact(BaseModel):
    """
    Contact/beneficiary model.
    Phone is unique per owner user; one contact may link to many bank accounts (BankAccount.contact).
    """

    class ContactRole(models.TextChoices):
        END_USER = 'end_user', 'End-user'
        MERCHANT = 'merchant', 'Merchant'
        DEALER = 'dealer', 'Dealer'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='contacts',
        db_index=True
    )
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=10, db_index=True)
    contact_role = models.CharField(
        max_length=20,
        choices=ContactRole.choices,
        default=ContactRole.END_USER,
        db_index=True,
    )
    
    class Meta:
        db_table = 'contacts'
        unique_together = [['user', 'phone']]
        indexes = [
            models.Index(fields=['user', 'phone']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.phone}"
