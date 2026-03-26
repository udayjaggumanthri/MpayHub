"""
Serializers for transactions app.
"""
from rest_framework import serializers
from apps.transactions.models import Transaction, PassbookEntry


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model."""
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'transaction_type', 'amount', 'charge', 'platform_fee',
            'net_amount', 'status', 'service_id', 'request_id', 'reference',
            'bill_type', 'biller', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PassbookEntrySerializer(serializers.ModelSerializer):
    """Serializer for PassbookEntry model."""
    
    class Meta:
        model = PassbookEntry
        fields = [
            'id', 'service', 'service_id', 'description', 'debit_amount',
            'credit_amount', 'opening_balance', 'closing_balance', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
