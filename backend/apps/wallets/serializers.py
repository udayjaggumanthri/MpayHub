"""
Serializers for wallets app.
"""
from rest_framework import serializers
from apps.wallets.models import Wallet, WalletTransaction


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
