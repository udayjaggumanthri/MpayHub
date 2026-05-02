"""
Serializers for BBPS app.
"""
from rest_framework import serializers
from urllib.parse import urlparse
import re
from apps.bbps.models import (
    BbpsBillerInputParam,
    BillPayment,
    BbpsBillerMaster,
    BbpsCategoryCommissionRule,
    BbpsProviderBillerMap,
    BbpsServiceCategory,
    BbpsServiceProvider,
    BbpsSyncUsageLog,
)
from apps.integrations.models import (
    BillAvenueAgentProfile,
    BillAvenueConfig,
    BillAvenueModeChannelPolicy,
)


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
    biller = serializers.CharField(max_length=200, required=False, allow_blank=True)
    biller_id = serializers.CharField(max_length=100, required=False)
    category = serializers.CharField(max_length=50, required=False, allow_blank=True)
    provider_id = serializers.IntegerField(required=False)
    init_channel = serializers.CharField(max_length=20, required=False, allow_blank=True)
    # Category-specific fields
    card_last4 = serializers.CharField(max_length=4, required=False)
    mobile = serializers.CharField(max_length=10, required=False)
    customer_number = serializers.CharField(max_length=50, required=False)
    input_params = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
    )


class BillPaymentCreateSerializer(serializers.Serializer):
    """Serializer for creating bill payment."""
    biller = serializers.CharField(max_length=200, required=False, allow_blank=True)
    biller_id = serializers.CharField(max_length=100, required=False)
    provider_id = serializers.IntegerField(required=False)
    bill_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    mpin = serializers.CharField(max_length=6, required=False, allow_blank=True, write_only=True)
    # Additional bill details
    customer_details = serializers.JSONField(required=False, default=dict)
    customer_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    remitter_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    biller_response = serializers.JSONField(required=False, default=dict)
    payment_mode = serializers.CharField(max_length=50, required=False, allow_blank=True)
    init_channel = serializers.CharField(max_length=20, required=False, allow_blank=True)
    agent_id = serializers.CharField(max_length=40, required=False, allow_blank=True)
    request_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    service_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    plan_id = serializers.CharField(max_length=60, required=False, allow_blank=True)
    input_params = serializers.JSONField(required=False, default=list)
    customer_info = serializers.JSONField(required=False, default=dict)
    agent_device_info = serializers.JSONField(required=False, default=dict)
    bill_payment_payload = serializers.JSONField(required=False, default=dict)


class BillAvenueConfigSerializer(serializers.ModelSerializer):
    """BillAvenue config; includes secret presence flags (no secret values)."""

    has_working_key = serializers.SerializerMethodField()
    has_iv = serializers.SerializerMethodField()
    has_callback_secret = serializers.SerializerMethodField()

    class Meta:
        model = BillAvenueConfig
        fields = [
            'id',
            'name',
            'mode',
            'api_format',
            'crypto_key_derivation',
            'enc_request_encoding',
            'allow_variant_fallback',
            'allow_txn_status_path_fallback',
            'base_url',
            'access_code',
            'institute_id',
            'request_version',
            'connect_timeout_seconds',
            'read_timeout_seconds',
            'max_retries',
            'mdm_refresh_hours',
            'mdm_max_calls_per_day',
            'push_callback_url',
            'enabled',
            'is_active',
            'activated_at',
            'created_at',
            'updated_at',
            'has_working_key',
            'has_iv',
            'has_callback_secret',
        ]
        read_only_fields = [
            'id',
            'activated_at',
            'created_at',
            'updated_at',
            'has_working_key',
            'has_iv',
            'has_callback_secret',
        ]

    def get_has_working_key(self, obj) -> bool:
        return bool((getattr(obj, 'working_key_encrypted', None) or '').strip())

    def get_has_iv(self, obj) -> bool:
        return bool((getattr(obj, 'iv_encrypted', None) or '').strip())

    def get_has_callback_secret(self, obj) -> bool:
        return bool((getattr(obj, 'callback_secret_encrypted', None) or '').strip())

    def validate(self, attrs):
        attrs = super().validate(attrs)
        mode = str(attrs.get('mode', getattr(self.instance, 'mode', '')) or '').lower()
        enabled = bool(attrs.get('enabled', getattr(self.instance, 'enabled', False)))
        is_active = bool(attrs.get('is_active', getattr(self.instance, 'is_active', False)))
        base_url = str(attrs.get('base_url', getattr(self.instance, 'base_url', '')) or '').strip()
        if mode in ('uat', 'prod') and (enabled or is_active):
            if not base_url:
                raise serializers.ValidationError({'base_url': 'Base URL is required for enabled/active UAT/PROD config.'})
            parsed = urlparse(base_url if '://' in base_url else f'https://{base_url}')
            if not parsed.scheme or not parsed.netloc:
                raise serializers.ValidationError({'base_url': 'Enter a valid URL with host, e.g. https://stgapi.billavenue.com'})
            attrs['base_url'] = f"{parsed.scheme}://{parsed.netloc}"
        return attrs


class BillAvenueSecretUpdateSerializer(serializers.Serializer):
    working_key = serializers.CharField(required=False, allow_blank=True)
    iv = serializers.CharField(required=False, allow_blank=True)
    callback_secret = serializers.CharField(required=False, allow_blank=True)


class BillAvenueAgentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillAvenueAgentProfile
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class BillAvenueModeChannelPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = BillAvenueModeChannelPolicy
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class BillerSyncRequestSerializer(serializers.Serializer):
    biller_ids = serializers.ListField(
        child=serializers.CharField(max_length=20), required=False, default=list
    )

    def validate_biller_ids(self, value):
        out = []
        seen = set()
        for raw in value or []:
            v = str(raw or '').strip()
            if not v:
                continue
            if not re.match(r'^[A-Za-z0-9\-_]+$', v):
                raise serializers.ValidationError(f'Invalid biller id: {v}')
            if v not in seen:
                seen.add(v)
                out.append(v)
        if len(out) > 2000:
            raise serializers.ValidationError('Maximum 2000 biller IDs are allowed per sync call.')
        return out


class StatusPollSerializer(serializers.Serializer):
    attempt_id = serializers.IntegerField(required=False)
    request_id = serializers.CharField(required=False, allow_blank=True)
    txn_ref_id = serializers.CharField(required=False, allow_blank=True)


class TransactionQuerySerializer(serializers.Serializer):
    tracking_type = serializers.ChoiceField(choices=['TRANS_REF_ID', 'MOBILE_NO', 'REQUEST_ID'])
    tracking_value = serializers.CharField(max_length=80)
    from_date = serializers.CharField(max_length=20, required=False, allow_blank=True)
    to_date = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get('tracking_type') == 'MOBILE_NO':
            if not attrs.get('from_date') or not attrs.get('to_date'):
                raise serializers.ValidationError('from_date and to_date are required for MOBILE_NO query.')
        return attrs


class ComplaintRegisterSerializer(serializers.Serializer):
    txn_ref_id = serializers.CharField(max_length=40)
    complaint_desc = serializers.CharField(max_length=255)
    complaint_disposition = serializers.CharField(max_length=255)


class ComplaintTrackSerializer(serializers.Serializer):
    complaint_id = serializers.CharField(max_length=60)


class PlanPullSerializer(serializers.Serializer):
    biller_ids = serializers.ListField(
        child=serializers.CharField(max_length=20), required=False, default=list
    )


class DepositEnquirySerializer(serializers.Serializer):
    from_date = serializers.CharField(max_length=25)
    to_date = serializers.CharField(max_length=25)
    trans_type = serializers.CharField(max_length=10, required=False, allow_blank=True, default='')
    agents = serializers.ListField(child=serializers.CharField(max_length=30), required=False, default=list)
    request_id = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    transaction_id = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')


class BbpsServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BbpsServiceCategory
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class BbpsBillerMasterLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BbpsBillerMaster
        fields = [
            'id', 'biller_id', 'biller_name', 'biller_category', 'biller_status',
            'last_synced_at', 'is_active_local', 'source_type', 'last_sync_status',
            'last_sync_error', 'soft_deleted_at', 'version',
        ]


class BbpsBillerInputParamSerializer(serializers.ModelSerializer):
    class Meta:
        model = BbpsBillerInputParam
        fields = [
            'param_name', 'data_type', 'is_optional', 'min_length', 'max_length',
            'regex', 'visibility', 'default_values', 'display_order',
        ]


class BbpsBillerMasterAdminSerializer(serializers.ModelSerializer):
    input_params = BbpsBillerInputParamSerializer(many=True, required=False)

    class Meta:
        model = BbpsBillerMaster
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_synced_at', 'version']


class BbpsSyncUsageLogSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source='requested_by.username', read_only=True)

    class Meta:
        model = BbpsSyncUsageLog
        fields = '__all__'


class BbpsServiceProviderSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source='category.code', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = BbpsServiceProvider
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'category_code', 'category_name']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        category = attrs.get('category') or getattr(self.instance, 'category', None)
        if category and not category.is_active:
            raise serializers.ValidationError({'category': 'Inactive category cannot be used.'})
        return attrs


class BbpsProviderBillerMapSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.name', read_only=True)
    provider_code = serializers.CharField(source='provider.code', read_only=True)
    category_code = serializers.CharField(source='provider.category.code', read_only=True)
    biller_id = serializers.CharField(source='biller_master.biller_id', read_only=True)
    biller_name = serializers.CharField(source='biller_master.biller_name', read_only=True)

    class Meta:
        model = BbpsProviderBillerMap
        fields = '__all__'
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'provider_name',
            'provider_code',
            'category_code',
            'biller_id',
            'biller_name',
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        provider = attrs.get('provider') or getattr(self.instance, 'provider', None)
        biller_master = attrs.get('biller_master') or getattr(self.instance, 'biller_master', None)
        if provider and not provider.is_active:
            raise serializers.ValidationError({'provider': 'Inactive provider cannot be mapped.'})
        if biller_master and biller_master.biller_status and str(biller_master.biller_status).upper() not in ('ACTIVE', 'ENABLED'):
            raise serializers.ValidationError({'biller_master': 'Only active/enabled billers should be mapped.'})
        eff_from = attrs.get('effective_from') or getattr(self.instance, 'effective_from', None)
        eff_to = attrs.get('effective_to') or getattr(self.instance, 'effective_to', None)
        if eff_from and eff_to and eff_from > eff_to:
            raise serializers.ValidationError({'effective_to': 'effective_to must be greater than effective_from.'})
        return attrs


class MdmCatalogPublishSerializer(serializers.Serializer):
    """Publish or unpublish a provider–biller map for end-user BBPS discovery."""

    map_id = serializers.IntegerField(min_value=1)
    published = serializers.BooleanField()


class BbpsCategoryCommissionRuleSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source='category.code', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = BbpsCategoryCommissionRule
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'category_code', 'category_name']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        category = attrs.get('category') or getattr(self.instance, 'category', None)
        if category and not category.is_active:
            raise serializers.ValidationError({'category': 'Inactive category cannot have active rules.'})
        eff_from = attrs.get('effective_from') or getattr(self.instance, 'effective_from', None)
        eff_to = attrs.get('effective_to') or getattr(self.instance, 'effective_to', None)
        if eff_from and eff_to and eff_from > eff_to:
            raise serializers.ValidationError({'effective_to': 'effective_to must be greater than effective_from.'})

        ctype = attrs.get('commission_type') or getattr(self.instance, 'commission_type', 'flat')
        value = attrs.get('value')
        if value is None and self.instance:
            value = self.instance.value
        if ctype == 'percentage' and value is not None and value > 100:
            raise serializers.ValidationError({'value': 'Percentage commission cannot be greater than 100.'})
        if ctype == 'percentage' and value is not None and value < 0:
            raise serializers.ValidationError({'value': 'Percentage commission must be non-negative.'})
        if ctype == 'flat' and value is not None and value < 0:
            raise serializers.ValidationError({'value': 'Flat commission must be non-negative.'})

        if attrs.get('is_active', getattr(self.instance, 'is_active', True)):
            if category is None:
                raise serializers.ValidationError({'category': 'category is required.'})
            q = BbpsCategoryCommissionRule.objects.filter(
                category=category,
                is_deleted=False,
                is_active=True,
            )
            if self.instance:
                q = q.exclude(pk=self.instance.pk)
            for row in q:
                row_from = row.effective_from
                row_to = row.effective_to
                proposed_from = eff_from
                proposed_to = eff_to
                starts_before_row_ends = (row_to is None) or (proposed_from is None) or (proposed_from <= row_to)
                row_starts_before_proposed_ends = (proposed_to is None) or (row_from is None) or (row_from <= proposed_to)
                if starts_before_row_ends and row_starts_before_proposed_ends:
                    raise serializers.ValidationError(
                        {'non_field_errors': ['Overlapping active commission rule exists for this category and effective window.']}
                    )
        return attrs
