"""
Serializers for BBPS app.
"""
from rest_framework import serializers
from apps.bbps.models import Biller, Bill, BillPayment


class BillerSerializer(serializers.ModelSerializer):
    """Serializer for Biller model."""
    
    class Meta:
        model = Biller
        fields = ['id', 'name', 'category', 'biller_id', 'is_active']
        read_only_fields = ['id']


class BillSerializer(serializers.ModelSerializer):
    """Serializer for Bill model."""
    biller = BillerSerializer(read_only=True)
    
    class Meta:
        model = Bill
        fields = ['id', 'biller', 'customer_details', 'amount', 'due_date', 'status']
        read_only_fields = ['id', 'status']


class BillPaymentSerializer(serializers.ModelSerializer):
    """Serializer for BillPayment model."""
    
    class Meta:
        model = BillPayment
        fields = [
            'id', 'biller', 'biller_id', 'bill_type', 'amount', 'charge',
            'total_deducted', 'status', 'service_id', 'request_id',
            'failure_reason', 'created_at'
        ]
        read_only_fields = [
            'id', 'charge', 'total_deducted', 'status', 'service_id',
            'request_id', 'failure_reason', 'created_at'
        ]


class FetchBillSerializer(serializers.Serializer):
    """Serializer for fetching bill."""
    biller = serializers.CharField(max_length=200)
    biller_id = serializers.CharField(max_length=100, required=False)
    category = serializers.CharField(max_length=50)
    # Category-specific fields
    card_last4 = serializers.CharField(max_length=4, required=False)
    mobile = serializers.CharField(max_length=10, required=False)
    customer_number = serializers.CharField(max_length=50, required=False)


class BillPaymentCreateSerializer(serializers.Serializer):
    """Serializer for creating bill payment."""
    biller = serializers.CharField(max_length=200)
    biller_id = serializers.CharField(max_length=100, required=False)
    bill_type = serializers.CharField(max_length=50)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    # Additional bill details
    customer_details = serializers.JSONField(required=False, default=dict)
