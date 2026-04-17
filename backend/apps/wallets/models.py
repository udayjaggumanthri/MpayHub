"""
Wallet models for the mPayhub platform.
"""
from django.db import models
from django.db.models import F
from django.db import transaction as db_transaction
from apps.core.models import BaseModel
from apps.authentication.models import User
from apps.core.exceptions import InsufficientBalance


class Wallet(BaseModel):
    """
    Wallet model for storing user balances.
    Each user has wallets for operations and earnings.
    """
    WALLET_TYPE_CHOICES = [
        ('main', 'Main Wallet'),
        ('commission', 'Commission Wallet'),
        ('bbps', 'BBPS Wallet'),
        ('profit', 'Profit Wallet'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wallets',
        db_index=True
    )
    wallet_type = models.CharField(
        max_length=20,
        choices=WALLET_TYPE_CHOICES,
        db_index=True
    )
    balance = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    
    class Meta:
        db_table = 'wallets'
        unique_together = [['user', 'wallet_type']]
        indexes = [
            models.Index(fields=['user', 'wallet_type']),
        ]
    
    def __str__(self):
        return f"{self.user.user_id} - {self.wallet_type} - ₹{self.balance}"
    
    @db_transaction.atomic
    def credit(self, amount, reference=None, description=None):
        """
        Credit amount to wallet.
        
        Args:
            amount: Amount to credit (Decimal)
            reference: Optional reference for the transaction
            description: Optional business description for history/reporting
        
        Returns:
            WalletTransaction object
        """
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
        
        # Update balance atomically
        Wallet.objects.filter(id=self.id).update(balance=F('balance') + amount)
        self.refresh_from_db()
        
        # Create transaction record
        transaction = WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='credit',
            reference=reference,
            description=description,
        )
        
        return transaction
    
    @db_transaction.atomic
    def debit(self, amount, reference=None, description=None):
        """
        Debit amount from wallet.
        
        Args:
            amount: Amount to debit (Decimal)
            reference: Optional reference for the transaction
            description: Optional business description for history/reporting
        
        Returns:
            WalletTransaction object
        
        Raises:
            InsufficientBalance: If wallet balance is insufficient
        """
        if amount <= 0:
            raise ValueError("Debit amount must be positive")
        
        # Check balance
        if self.balance < amount:
            raise InsufficientBalance(
                f"Insufficient balance in {self.wallet_type} wallet. "
                f"Available: ₹{self.balance}, Required: ₹{amount}"
            )
        
        # Update balance atomically
        Wallet.objects.filter(id=self.id).update(balance=F('balance') - amount)
        self.refresh_from_db()
        
        # Create transaction record
        transaction = WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='debit',
            reference=reference,
            description=description,
        )
        
        return transaction
    
    @classmethod
    def get_wallet(cls, user, wallet_type):
        """
        Get or create wallet for user.
        
        Args:
            user: User object
            wallet_type: Wallet type (main, commission, bbps, profit)
        
        Returns:
            Wallet object
        """
        wallet, created = cls.objects.get_or_create(
            user=user,
            wallet_type=wallet_type,
            defaults={'balance': 0.00}
        )
        return wallet


class WalletTransaction(BaseModel):
    """
    Wallet transaction history.
    """
    TRANSACTION_TYPE_CHOICES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]
    
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transactions',
        db_index=True
    )
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    reference = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'wallet_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', 'created_at']),
            models.Index(fields=['transaction_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.wallet.wallet_type} - {self.transaction_type} - ₹{self.amount}"
