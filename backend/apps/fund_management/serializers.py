"""
Serializers for fund management app.
"""
from rest_framework import serializers
from apps.fund_management.models import LoadMoney, Payout
from apps.bank_accounts.serializers import BankAccountSerializer


class LoadMoneySerializer(serializers.ModelSerializer):
    """Serializer for LoadMoney model."""
    
    class Meta:
        model = LoadMoney
        fields = [
            'id', 'amount', 'gateway', 'charge', 'net_credit',
            'status', 'transaction_id', 'gateway_transaction_id',
            'failure_reason', 'created_at'
        ]
        read_only_fields = [
            'id', 'charge', 'net_credit', 'status', 'transaction_id',
            'gateway_transaction_id', 'failure_reason', 'created_at'
        ]


class PayoutSerializer(serializers.ModelSerializer):
    """Serializer for Payout model."""
    bank_account = BankAccountSerializer(read_only=True)
    bank_account_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Payout
        fields = [
            'id', 'bank_account', 'bank_account_id', 'amount', 'charge',
            'platform_fee', 'total_deducted', 'status', 'transaction_id',
            'gateway_transaction_id', 'failure_reason', 'created_at'
        ]
        read_only_fields = [
            'id', 'charge', 'platform_fee', 'total_deducted', 'status',
            'transaction_id', 'gateway_transaction_id', 'failure_reason', 'created_at'
        ]
