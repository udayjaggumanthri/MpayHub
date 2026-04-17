"""
Serializers for wallets app.
"""
from decimal import Decimal

from rest_framework import serializers
from apps.wallets.models import Wallet, WalletTransaction
from apps.core.utils import validate_mpin


class WalletSerializer(serializers.ModelSerializer):
    """Serializer for Wallet model."""
    
    class Meta:
        model = Wallet
        fields = ['id', 'wallet_type', 'balance', 'created_at', 'updated_at']
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at']


class WalletTransactionSerializer(serializers.ModelSerializer):
    """Serializer for WalletTransaction model."""
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'wallet', 'amount', 'transaction_type',
            'reference', 'description', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class WalletListSerializer(serializers.Serializer):
    """Serializer for listing all wallets of a user."""
    main = WalletSerializer()
    commission = WalletSerializer(required=False)
    bbps = WalletSerializer()
    profit = WalletSerializer(required=False)


class MainToBbpsTransferSerializer(serializers.Serializer):
    """Move funds from main wallet to BBPS wallet (MPIN required)."""

    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    mpin = serializers.CharField(write_only=True, max_length=6, min_length=6)

    def validate_mpin(self, value):
        if not validate_mpin(value):
            raise serializers.ValidationError('MPIN must be 6 digits.')
        return value
