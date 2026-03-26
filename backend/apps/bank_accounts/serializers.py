"""
Serializers for bank_accounts app.
"""
from rest_framework import serializers
from apps.bank_accounts.models import BankAccount
from apps.core.utils import validate_ifsc


class BankAccountSerializer(serializers.ModelSerializer):
    """Serializer for BankAccount model."""
    
    class Meta:
        model = BankAccount
        fields = [
            'id', 'contact', 'account_number', 'ifsc', 'bank_name',
            'account_holder_name', 'beneficiary_name', 'is_verified',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'beneficiary_name', 'is_verified', 'created_at', 'updated_at']
    
    def validate_ifsc(self, value):
        """Validate IFSC code."""
        if not validate_ifsc(value):
            raise serializers.ValidationError("Invalid IFSC code format.")
        return value.upper()


class BankAccountValidationSerializer(serializers.Serializer):
    """Serializer for bank account validation."""
    account_number = serializers.CharField(max_length=20)
    ifsc = serializers.CharField(max_length=11)
    
    def validate_ifsc(self, value):
        """Validate IFSC code."""
        if not validate_ifsc(value):
            raise serializers.ValidationError("Invalid IFSC code format.")
        return value.upper()
