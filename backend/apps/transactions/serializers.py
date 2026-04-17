"""
Serializers for transactions app.
"""
from decimal import Decimal

from rest_framework import serializers

from apps.transactions.models import Transaction, PassbookEntry, CommissionLedger


def _dec4(v):
    if v is None:
        return None
    return str(Decimal(str(v)).quantize(Decimal('0.0001')))


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model."""

    actor_user_id = serializers.CharField(source='user.user_id', read_only=True)
    amount = serializers.SerializerMethodField()
    charge = serializers.SerializerMethodField()
    platform_fee = serializers.SerializerMethodField()
    net_amount = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            'id',
            'transaction_type',
            'amount',
            'charge',
            'platform_fee',
            'net_amount',
            'status',
            'service_id',
            'request_id',
            'reference',
            'bill_type',
            'biller',
            'created_at',
            'actor_user_id',
            'agent_user',
            'agent_role_at_time',
            'agent_user_code',
            'agent_name_snapshot',
            'service_family',
            'bank_txn_id',
            'card_last4',
        ]
        read_only_fields = fields

    def get_amount(self, obj):
        return _dec4(obj.amount)

    def get_charge(self, obj):
        return _dec4(obj.charge)

    def get_platform_fee(self, obj):
        return _dec4(obj.platform_fee)

    def get_net_amount(self, obj):
        return _dec4(obj.net_amount)


class PassbookEntrySerializer(serializers.ModelSerializer):
    """Serializer for PassbookEntry model."""

    owner_user_id = serializers.CharField(source='user.user_id', read_only=True)
    debit_amount = serializers.SerializerMethodField()
    credit_amount = serializers.SerializerMethodField()
    opening_balance = serializers.SerializerMethodField()
    closing_balance = serializers.SerializerMethodField()
    service_charge = serializers.SerializerMethodField()
    principal_amount = serializers.SerializerMethodField()

    class Meta:
        model = PassbookEntry
        fields = [
            'id',
            'wallet_type',
            'service',
            'service_id',
            'description',
            'debit_amount',
            'credit_amount',
            'opening_balance',
            'closing_balance',
            'service_charge',
            'principal_amount',
            'created_at',
            'owner_user_id',
            'initiator_user',
            'initiator_role_at_time',
            'initiator_user_code',
            'initiator_name_snapshot',
        ]
        read_only_fields = fields

    def get_debit_amount(self, obj):
        return _dec4(obj.debit_amount)

    def get_credit_amount(self, obj):
        return _dec4(obj.credit_amount)

    def get_opening_balance(self, obj):
        return _dec4(obj.opening_balance)

    def get_closing_balance(self, obj):
        return _dec4(obj.closing_balance)

    def get_service_charge(self, obj):
        return _dec4(obj.service_charge)

    def get_principal_amount(self, obj):
        return _dec4(obj.principal_amount)


class CommissionLedgerSerializer(serializers.ModelSerializer):
    """Pay-in commission audit rows (includes source agent in meta)."""

    amount = serializers.SerializerMethodField()

    class Meta:
        model = CommissionLedger
        fields = [
            'id',
            'user',
            'role_at_time',
            'amount',
            'source',
            'reference_service_id',
            'wallet_type',
            'meta',
            'created_at',
            'source_user_code',
            'source_role',
            'source_name_snapshot',
        ]
        read_only_fields = fields

    def get_amount(self, obj):
        return _dec4(obj.amount)
