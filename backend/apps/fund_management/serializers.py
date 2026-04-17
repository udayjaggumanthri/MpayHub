"""
Serializers for fund management app.
"""
from decimal import Decimal

from rest_framework import serializers

from apps.core.utils import validate_mpin
from apps.fund_management.models import LoadMoney, PayInPackage, Payout
from apps.bank_accounts.serializers import BankAccountSerializer


def payin_payment_mode_display(obj: LoadMoney) -> str:
    """Human label for reports (UPI, Net Banking, cards, etc.)."""
    pm = (obj.payment_method or '').strip().lower()
    meta = obj.payment_meta if isinstance(obj.payment_meta, dict) else {}
    st = (obj.status or '').upper()
    if not pm:
        if st == 'PENDING':
            return 'Pending'
        if st == 'FAILED':
            return '—'
        return 'Not recorded'
    if pm == 'mock':
        return 'Test / Mock'
    if pm == 'card':
        ct = str(meta.get('card_type') or '').lower()
        if ct == 'credit':
            return 'Credit Card'
        if ct == 'debit':
            return 'Debit Card'
        if ct == 'prepaid':
            return 'Prepaid Card'
        return 'Credit / Debit Card'
    labels = {
        'upi': 'UPI',
        'netbanking': 'Net Banking',
        'wallet': 'Wallet',
        'emi': 'EMI',
        'paylater': 'Pay Later',
        'nach': 'NACH',
        'otp': 'OTP',
        'cardless_emi': 'Cardless EMI',
    }
    return labels.get(pm, pm.replace('_', ' ').title())


def payin_payment_gateway_name(obj: LoadMoney) -> str:
    """Configured PaymentGateway name, else provider / package label."""
    pkg = getattr(obj, 'package', None)
    if not pkg:
        return '—'
    pg = getattr(pkg, 'payment_gateway', None)
    if pg and getattr(pg, 'name', None):
        return pg.name
    prov = (getattr(pkg, 'provider', '') or '').strip().lower()
    if prov == 'razorpay':
        return 'Razorpay'
    if prov == 'payu':
        return 'PayU'
    if prov == 'mock':
        return 'Mock (test)'
    return (pkg.display_name or pkg.code or '—') or '—'


class PayInPackageSerializer(serializers.ModelSerializer):
    """Active pay-in packages for dropdown / quote."""

    class Meta:
        model = PayInPackage
        fields = [
            'id',
            'code',
            'display_name',
            'provider',
            'min_amount',
            'max_amount_per_txn',
            'gateway_fee_pct',
            'admin_pct',
            'super_distributor_pct',
            'master_distributor_pct',
            'distributor_pct',
            'retailer_commission_pct',
            'is_active',
            'is_default',
            'sort_order',
        ]
        read_only_fields = fields


class LoadMoneySerializer(serializers.ModelSerializer):
    """Serializer for LoadMoney model (read/update shape)."""

    payment_mode_display = serializers.SerializerMethodField()
    payment_gateway_name = serializers.SerializerMethodField()

    class Meta:
        model = LoadMoney
        fields = [
            'id',
            'package',
            'amount',
            'gateway',
            'charge',
            'net_credit',
            'fee_breakdown_snapshot',
            'customer_name',
            'customer_email',
            'customer_phone',
            'provider_order_id',
            'payment_method',
            'payment_meta',
            'payment_mode_display',
            'payment_gateway_name',
            'status',
            'transaction_id',
            'gateway_transaction_id',
            'failure_reason',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'charge',
            'net_credit',
            'status',
            'transaction_id',
            'gateway_transaction_id',
            'failure_reason',
            'created_at',
            'payment_method',
            'payment_meta',
            'payment_mode_display',
            'payment_gateway_name',
        ]

    def get_payment_mode_display(self, obj):
        return payin_payment_mode_display(obj)

    def get_payment_gateway_name(self, obj):
        return payin_payment_gateway_name(obj)


class LegacyLoadMoneyCreateSerializer(serializers.Serializer):
    """POST /load-money/ legacy body: amount + optional gateway id."""

    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    gateway = serializers.IntegerField(required=False, allow_null=True)


class PayInQuoteSerializer(serializers.Serializer):
    package_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))


class PayInCreateOrderSerializer(serializers.Serializer):
    package_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    contact_id = serializers.IntegerField(min_value=1)


class PayInMockCompleteSerializer(serializers.Serializer):
    transaction_id = serializers.CharField(max_length=100)


class PayInRazorpayVerifySerializer(serializers.Serializer):
    """POST pay-in/verify-razorpay/ — body from Razorpay Checkout handler."""

    transaction_id = serializers.CharField(max_length=100)
    razorpay_order_id = serializers.CharField(max_length=191)
    razorpay_payment_id = serializers.CharField(max_length=191)
    razorpay_signature = serializers.CharField(max_length=500)


class PayoutSerializer(serializers.ModelSerializer):
    """Serializer for Payout model."""

    bank_account = BankAccountSerializer(read_only=True)
    bank_account_id = serializers.IntegerField(write_only=True)
    mpin = serializers.CharField(write_only=True, max_length=6, min_length=6)
    gateway = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Payout
        fields = [
            'id',
            'bank_account',
            'bank_account_id',
            'amount',
            'charge',
            'platform_fee',
            'total_deducted',
            'transfer_mode',
            'status',
            'transaction_id',
            'gateway_transaction_id',
            'failure_reason',
            'created_at',
            'mpin',
            'gateway',
        ]
        read_only_fields = [
            'id',
            'charge',
            'platform_fee',
            'total_deducted',
            'status',
            'transaction_id',
            'gateway_transaction_id',
            'failure_reason',
            'created_at',
        ]
        extra_kwargs = {
            'transfer_mode': {'required': False, 'default': 'IMPS'},
        }

    def validate_mpin(self, value):
        if not validate_mpin(value):
            raise serializers.ValidationError('MPIN must be 6 digits.')
        return value


class PayoutQuoteSerializer(serializers.Serializer):
    """Optional amount to preview charge + total debit."""

    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
