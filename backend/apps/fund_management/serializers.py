"""
Serializers for fund management app.
"""
from decimal import Decimal

from rest_framework import serializers

from apps.core.utils import validate_mpin
from apps.fund_management.models import LoadMoney, PayInPackage, Payout
from apps.fund_management.payin_rail_labels import payin_collection_method_label, payin_is_qr_rail
from apps.bank_accounts.serializers import BankAccountSerializer


def payin_payment_mode_display(obj: LoadMoney) -> str:
    """Human label for reports (UPI, Net Banking, cards, etc.)."""
    if payin_is_qr_rail(obj):
        st = (obj.status or '').upper()
        if st == 'PENDING_REVIEW':
            return 'Manual QR — Pending review'
        base = 'Manual QR'
        pm = (obj.payment_method or '').strip().lower()
        if pm:
            channel_labels = {
                'upi': 'UPI',
                'mock': 'Test / Mock',
            }
            if pm in channel_labels:
                return f'{base} ({channel_labels[pm]})'
        return base
    return _payin_payment_mode_display_gateway(obj)


def _payin_payment_mode_display_gateway(obj: LoadMoney) -> str:
    pm = (obj.payment_method or '').strip().lower()
    meta = obj.payment_meta if isinstance(obj.payment_meta, dict) else {}
    st = (obj.status or '').upper()
    if not pm:
        if st == 'PENDING':
            return 'Pending'
        if st == 'PENDING_REVIEW':
            return 'QR — Pending review'
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
    """Configured collection method: QR account or payment gateway."""
    return payin_collection_method_label(obj)


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


class LoadMoneyListSerializer(serializers.ModelSerializer):
    """Lite list serializer — omits heavy payment_meta blob."""

    payment_mode_display = serializers.SerializerMethodField()
    payment_gateway_name = serializers.SerializerMethodField()
    reject_reason = serializers.SerializerMethodField()

    class Meta:
        model = LoadMoney
        fields = [
            'id',
            'package',
            'amount',
            'gateway',
            'charge',
            'net_credit',
            'customer_name',
            'customer_email',
            'customer_phone',
            'provider_order_id',
            'payment_method',
            'payment_mode_display',
            'payment_gateway_name',
            'status',
            'transaction_id',
            'gateway_transaction_id',
            'failure_reason',
            'collection_rail',
            'utr',
            'payment_date',
            'submitted_amount',
            'reject_reason',
            'reviewed_at',
            'created_at',
        ]
        read_only_fields = fields

    def get_reject_reason(self, obj):
        if (getattr(obj, 'collection_rail', None) or '') == 'qr' and (obj.status or '') == 'FAILED':
            return (obj.failure_reason or '').strip()
        return ''

    def get_payment_mode_display(self, obj):
        return payin_payment_mode_display(obj)

    def get_payment_gateway_name(self, obj):
        return payin_payment_gateway_name(obj)


class LoadMoneySerializer(serializers.ModelSerializer):
    """Serializer for LoadMoney model (read/update shape)."""

    payment_mode_display = serializers.SerializerMethodField()
    payment_gateway_name = serializers.SerializerMethodField()
    fee_breakdown_snapshot = serializers.SerializerMethodField()
    reject_reason = serializers.SerializerMethodField()

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
            'collection_rail',
            'utr',
            'payment_date',
            'submitted_amount',
            'reject_reason',
            'reviewed_at',
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
            'collection_rail',
            'utr',
            'payment_date',
            'submitted_amount',
            'reviewed_at',
            'payment_method',
            'payment_meta',
            'payment_mode_display',
            'payment_gateway_name',
            'fee_breakdown_snapshot',
        ]

    def get_reject_reason(self, obj):
        if (getattr(obj, 'collection_rail', None) or '') == 'qr' and (obj.status or '') == 'FAILED':
            return (obj.failure_reason or '').strip()
        return ''

    def get_fee_breakdown_snapshot(self, obj):
        raw = obj.fee_breakdown_snapshot if isinstance(obj.fee_breakdown_snapshot, dict) else {}
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        if user and getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) == 'Admin':
            return raw
        return {}

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
    gateway_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)


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
