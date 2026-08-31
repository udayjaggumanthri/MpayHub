"""Serializers for manual QR pay-in."""
import json
import mimetypes
from decimal import Decimal

from django.urls import reverse
from rest_framework import serializers

from apps.fund_management.models import LoadMoney, PayInQrAccount, PayInQrApprovalAudit
from apps.fund_management.qr_approval import REJECT_REASON_CODES
def _coerce_bank_details(value):
    if value in (None, '', {}):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {'note': raw}
        except json.JSONDecodeError:
            return {'note': raw}
    return {}


class PayInQrAccountSerializer(serializers.ModelSerializer):
    qr_image_url = serializers.SerializerMethodField()

    class Meta:
        model = PayInQrAccount
        fields = [
            'id',
            'display_name',
            'qr_image',
            'qr_image_url',
            'account_display_name',
            'upi_vpa',
            'bank_details',
            'sort_order',
            'status',
            'daily_limit_24h',
            'max_per_txn',
            'charge_rate',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'qr_image_url']

    def validate_bank_details(self, value):
        return _coerce_bank_details(value)

    def get_qr_image_url(self, obj):
        if not obj.qr_image:
            return ''
        request = self.context.get('request')
        try:
            url = obj.qr_image.url
            if request:
                return request.build_absolute_uri(url)
            return url
        except Exception:
            return ''


class PayInQrSubmitSerializer(serializers.Serializer):
    package_id = serializers.IntegerField(min_value=1)
    qr_account_id = serializers.IntegerField(min_value=1)
    contact_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal('0.01'))
    utr = serializers.CharField(max_length=64)
    payment_date = serializers.DateField()
    receipt = serializers.ImageField()


class QrPayInApproveSerializer(serializers.Serializer):
    approved_amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal('0.01'))
    internal_note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class QrPayInRejectSerializer(serializers.Serializer):
    reason_code = serializers.ChoiceField(choices=[c[0] for c in REJECT_REASON_CODES])
    reason_text = serializers.CharField(required=False, allow_blank=True, max_length=500)
    internal_note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class QrPayInReleaseUtrSerializer(serializers.Serializer):
    internal_note = serializers.CharField(min_length=10, max_length=2000)


class PayInQrApprovalAuditSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = PayInQrApprovalAudit
        fields = [
            'id',
            'action',
            'actor',
            'actor_name',
            'submitted_amount',
            'approved_amount',
            'reject_reason',
            'internal_note',
            'created_at',
        ]

    def get_actor_name(self, obj):
        if not obj.actor:
            return ''
        prof = getattr(obj.actor, 'profile', None)
        if prof and getattr(prof, 'full_name', None):
            return prof.full_name
        return getattr(obj.actor, 'email', '') or str(obj.actor_id)


class QrPayInOperationListSerializer(serializers.ModelSerializer):
    user_code = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    qr_account_name = serializers.SerializerMethodField()
    receipt_url = serializers.SerializerMethodField()
    reviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = LoadMoney
        fields = [
            'id',
            'transaction_id',
            'created_at',
            'status',
            'collection_rail',
            'amount',
            'submitted_amount',
            'charge',
            'net_credit',
            'utr',
            'payment_date',
            'customer_name',
            'customer_phone',
            'failure_reason',
            'user_id',
            'user_code',
            'user_name',
            'user_role',
            'pay_in_qr_account_id',
            'qr_account_name',
            'package_id',
            'receipt_url',
            'reviewed_at',
            'reviewer_name',
        ]

    def get_user_code(self, obj):
        from apps.users.identity import public_display_code

        return public_display_code(obj.user) if obj.user else ''

    def get_user_name(self, obj):
        if not obj.user:
            return ''
        prof = getattr(obj.user, 'profile', None)
        if prof and getattr(prof, 'full_name', None):
            return prof.full_name
        return obj.customer_name or ''

    def get_user_role(self, obj):
        return getattr(obj.user, 'role', '') if obj.user else ''

    def get_qr_account_name(self, obj):
        qr = obj.pay_in_qr_account
        return qr.display_name if qr else (obj.gateway or '')

    def get_receipt_url(self, obj):
        if not obj.receipt_image:
            return ''
        request = self.context.get('request')
        try:
            path = reverse(
                'fund_management:pay-in-qr-receipt',
                kwargs={'transaction_id': obj.transaction_id},
            )
            if request:
                return request.build_absolute_uri(path)
            return path
        except Exception:
            return ''

    def get_reviewer_name(self, obj):
        if not obj.reviewed_by:
            return ''
        prof = getattr(obj.reviewed_by, 'profile', None)
        if prof and getattr(prof, 'full_name', None):
            return prof.full_name
        return getattr(obj.reviewed_by, 'email', '') or ''


class QrPayInOperationDetailSerializer(QrPayInOperationListSerializer):
    fee_breakdown_snapshot = serializers.SerializerMethodField()
    audits = PayInQrApprovalAuditSerializer(source='qr_approval_audits', many=True, read_only=True)

    class Meta(QrPayInOperationListSerializer.Meta):
        fields = QrPayInOperationListSerializer.Meta.fields + [
            'fee_breakdown_snapshot',
            'audits',
            'payment_meta',
        ]

    def get_fee_breakdown_snapshot(self, obj):
        raw = obj.fee_breakdown_snapshot if isinstance(obj.fee_breakdown_snapshot, dict) else {}
        return raw
