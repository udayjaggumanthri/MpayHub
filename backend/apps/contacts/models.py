"""
Contact models for the mPayhub platform.
"""
from django.db import models
from apps.core.models import BaseModel
from apps.authentication.models import User


class Contact(BaseModel):
    """
    Contact/beneficiary model.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='contacts',
        db_index=True
    )
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=10, db_index=True)
    
    class Meta:
        db_table = 'contacts'
        unique_together = [['user', 'phone']]
        indexes = [
            models.Index(fields=['user', 'phone']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.phone}"
