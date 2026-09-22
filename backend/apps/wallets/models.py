"""
Wallet models for the mPayhub platform.

Post-consolidation: only ``main`` is a live spendable balance.
Legacy wallet_type rows (bbps/commission/profit) remain readable but are archived.
"""
from decimal import Decimal

from django.db import models
from django.db.models import F
from django.db import transaction as db_transaction

from apps.core.models import BaseModel
from apps.authentication.models import User
from apps.core.exceptions import InsufficientBalance


class Wallet(BaseModel):
    """
    Wallet model for storing user balances.
    Each user has a primary ``main`` wallet. Legacy types are retained for audit.
    """
    WALLET_TYPE_CHOICES = [
        ('main', 'Main Wallet'),
        ('commission', 'Commission Wallet'),
        ('bbps', 'BBPS Wallet'),
        ('profit', 'Profit Wallet'),
    ]

    ACTIVE_WALLET_TYPE = 'main'
    LEGACY_WALLET_TYPES = ('commission', 'bbps', 'profit')

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
    held_balance = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=0,
        help_text='Amount reserved for in-flight operations (BBPS AWAITED, CMS holds).',
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text='True after consolidation drained this non-main wallet to zero.',
    )

    class Meta:
        db_table = 'wallets'
        unique_together = [['user', 'wallet_type']]
        indexes = [
            models.Index(fields=['user', 'wallet_type']),
        ]

    def __str__(self):
        return f"{self.user.user_id} - {self.wallet_type} - ₹{self.balance}"

    @property
    def available_balance(self) -> Decimal:
        """Spendable balance after holds."""
        bal = Decimal(str(self.balance or 0))
        held = Decimal(str(self.held_balance or 0))
        avail = bal - held
        return avail if avail > 0 else Decimal('0')

    @db_transaction.atomic
    def credit(self, amount, reference=None, description=None):
        """Credit amount to wallet."""
        if amount <= 0:
            raise ValueError("Credit amount must be positive")

        Wallet.objects.filter(id=self.id).update(balance=F('balance') + amount)
        self.refresh_from_db()

        return WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='credit',
            reference=reference,
            description=description,
        )

    @db_transaction.atomic
    def debit(self, amount, reference=None, description=None, *, respect_holds=True):
        """
        Debit amount from wallet.

        When ``respect_holds`` is True (default), available_balance is checked
        so held funds cannot be spent. Pass ``respect_holds=False`` for
        consolidation bridge debits that drain archived wallets in full.
        """
        if amount <= 0:
            raise ValueError("Debit amount must be positive")

        self.refresh_from_db()
        check_against = self.available_balance if respect_holds else Decimal(str(self.balance or 0))
        if check_against < amount:
            raise InsufficientBalance(
                f"Insufficient balance in {self.wallet_type} wallet. "
                f"Available: ₹{check_against}, Required: ₹{amount}"
            )

        Wallet.objects.filter(id=self.id).update(balance=F('balance') - amount)
        self.refresh_from_db()

        return WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='debit',
            reference=reference,
            description=description,
        )

    @db_transaction.atomic
    def hold(self, amount, reference=None, description=None):
        """
        Reserve ``amount`` from available balance without changing ``balance``.
        Used for in-flight BBPS / CMS operations.
        """
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Hold amount must be positive")

        locked = Wallet.objects.select_for_update().get(pk=self.pk)
        avail = Decimal(str(locked.balance or 0)) - Decimal(str(locked.held_balance or 0))
        if avail < amount:
            raise InsufficientBalance(
                f"Insufficient available balance for hold. "
                f"Available: ₹{avail}, Required: ₹{amount}"
            )
        Wallet.objects.filter(pk=locked.pk).update(held_balance=F('held_balance') + amount)
        self.refresh_from_db()
        return WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='hold',
            reference=reference,
            description=description or 'Hold',
        )

    @db_transaction.atomic
    def release(self, amount, reference=None, description=None):
        """Release a previously held amount back to available (no balance change)."""
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Release amount must be positive")

        locked = Wallet.objects.select_for_update().get(pk=self.pk)
        held = Decimal(str(locked.held_balance or 0))
        if held < amount:
            raise ValueError(
                f"Cannot release ₹{amount}; only ₹{held} is held"
            )
        Wallet.objects.filter(pk=locked.pk).update(held_balance=F('held_balance') - amount)
        self.refresh_from_db()
        return WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='release',
            reference=reference,
            description=description or 'Release hold',
        )

    @db_transaction.atomic
    def settle_hold(self, amount, reference=None, description=None):
        """
        Convert a hold into a real debit: reduce held_balance AND balance.
        """
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Settle amount must be positive")

        locked = Wallet.objects.select_for_update().get(pk=self.pk)
        held = Decimal(str(locked.held_balance or 0))
        bal = Decimal(str(locked.balance or 0))
        if held < amount:
            raise ValueError(f"Cannot settle ₹{amount}; only ₹{held} is held")
        if bal < amount:
            raise InsufficientBalance(
                f"Insufficient balance to settle hold. Balance: ₹{bal}, Required: ₹{amount}"
            )
        Wallet.objects.filter(pk=locked.pk).update(
            held_balance=F('held_balance') - amount,
            balance=F('balance') - amount,
        )
        self.refresh_from_db()
        return WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='settle',
            reference=reference,
            description=description or 'Settle hold',
        )

    @classmethod
    def get_wallet(cls, user, wallet_type):
        """
        Get or create wallet for user.

        For live money movement prefer ``wallet_type='main'``.
        Legacy types are still get_or_create'd for historical reads.
        """
        wallet, _created = cls.objects.get_or_create(
            user=user,
            wallet_type=wallet_type,
            defaults={'balance': 0.00, 'held_balance': 0.00},
        )
        return wallet


class WalletTransaction(BaseModel):
    """Wallet transaction history."""
    TRANSACTION_TYPE_CHOICES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
        ('hold', 'Hold'),
        ('release', 'Release'),
        ('settle', 'Settle'),
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


class WalletMergeAudit(BaseModel):
    """
    Per-user snapshot of the wallet consolidation.

    Written by the consolidation migration / dry-run. Source of truth for
    rollback and post-merge reconciliation.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('merged', 'Merged'),
        ('rolled_back', 'Rolled back'),
        ('dry_run', 'Dry run'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wallet_merge_audits',
        db_index=True,
    )
    main_before = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    bbps_before = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    commission_before = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    profit_before = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    merged_total = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=0,
        help_text='Sum of all source balances folded into main (excludes main_before).',
    )
    main_after = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    bridge_service_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'wallet_merge_audits'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"MergeAudit {self.user_id} {self.status} merged={self.merged_total}"
