from decimal import Decimal

from rest_framework import serializers
from django.utils.text import slugify

from apps.core.utils import decrypt_secret_payload, encrypt_secret_payload
from apps.integrations.models import ApiMaster
from apps.integrations.razorpay_orders import (
    extract_razorpay_key_pair_from_secrets,
    is_razorpay_like_provider_code,
)


REQUIRED_SECRETS_BY_PROVIDER = {
    'aadhaar_ekyc': ['client_id', 'client_secret'],
    'pan_verify': ['api_key'],
    'razorpay': ['key_id', 'key_secret'],
    'payu': ['merchant_key', 'merchant_salt'],
}


def _mask_secret_value(value):
    text = str(value or '')
    if not text:
        return ''
    if len(text) <= 4:
        return '*' * len(text)
    return f"{'*' * max(3, len(text) - 4)}{text[-4:]}"


class ApiMasterSerializer(serializers.ModelSerializer):
    # Do not apply DRF's auto unique validator on provider_type.
    # Business rule is: only one *default* per provider_type, not one total row.
    provider_type = serializers.ChoiceField(
        choices=ApiMaster.PROVIDER_TYPE_CHOICES,
        required=True,
        validators=[],
    )
    secrets = serializers.DictField(write_only=True, required=False)
    secrets_masked = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ApiMaster
        fields = [
            'id',
            'provider_code',
            'provider_name',
            'provider_type',
            'base_url',
            'auth_type',
            'config_json',
            'status',
            'priority',
            'is_default',
            'supports_webhook',
            'webhook_path',
            'secrets',
            'secrets_masked',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'secrets_masked']

    def get_secrets_masked(self, obj):
        payload = decrypt_secret_payload(obj.secrets_encrypted or '')
        return {k: _mask_secret_value(v) for k, v in payload.items()}

    def validate_provider_code(self, value):
        normalized = slugify(str(value or ''), allow_unicode=False)
        if not normalized:
            raise serializers.ValidationError(
                'Provider code must contain letters or numbers.'
            )
        return normalized

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = getattr(self, 'instance', None)
        provider_code = attrs.get('provider_code', getattr(instance, 'provider_code', '')).strip()
        base_url = attrs.get('base_url', getattr(instance, 'base_url', ''))
        if provider_code != 'custom' and not base_url:
            raise serializers.ValidationError({'base_url': ['Base URL is required for provider configuration.']})

        for key in ('priority',):
            value = attrs.get(key, getattr(instance, key, 0))
            if Decimal(str(value)) < 0:
                raise serializers.ValidationError({key: ['Must be greater than or equal to 0.']})

        provider_type = attrs.get('provider_type', getattr(instance, 'provider_type', '')).strip().lower()
        is_default = bool(attrs.get('is_default', getattr(instance, 'is_default', False)))
        if is_default and provider_type:
            existing_default = ApiMaster.objects.filter(
                provider_type=provider_type,
                is_default=True,
                is_deleted=False,
            )
            if instance is not None:
                existing_default = existing_default.exclude(pk=instance.pk)
            if existing_default.exists():
                raise serializers.ValidationError(
                    {'is_default': ['A default API master already exists for this module. Uncheck default or edit existing default entry.']}
                )

        incoming_raw = attrs.get('secrets')
        decrypted_existing = decrypt_secret_payload(getattr(instance, 'secrets_encrypted', '') or '')

        pc_norm = provider_code.strip().lower()
        rules_code = 'razorpay' if is_razorpay_like_provider_code(provider_code) else pc_norm

        if incoming_raw is not None:
            # Drop empty strings so UI rows with blank "Value" do not wipe stored secrets on update.
            incoming_clean = {
                k: v
                for k, v in incoming_raw.items()
                if v is not None and str(v).strip() != ''
            }
            merged = {**decrypted_existing, **incoming_clean}

            # Backward-compatible aliases + canonical key_id/key_secret for Razorpay-like providers.
            if rules_code == 'razorpay':
                if not merged.get('key_id') and merged.get('api_key'):
                    merged['key_id'] = merged.get('api_key')
                if not merged.get('key_secret') and merged.get('api_secret'):
                    merged['key_secret'] = merged.get('api_secret')
                kid, ksec = extract_razorpay_key_pair_from_secrets(merged)
                if kid:
                    merged['key_id'] = kid
                if ksec:
                    merged['key_secret'] = ksec
            if pc_norm == 'payu':
                if not merged.get('merchant_key') and merged.get('api_key'):
                    merged['merchant_key'] = merged.get('api_key')
                if not merged.get('merchant_salt') and merged.get('api_secret'):
                    merged['merchant_salt'] = merged.get('api_secret')

            required_keys = REQUIRED_SECRETS_BY_PROVIDER.get(rules_code, [])
            missing = [key for key in required_keys if not str(merged.get(key, '')).strip()]
            if missing:
                raise serializers.ValidationError({'secrets': [f"Missing required keys: {', '.join(missing)}"]})

            attrs['secrets'] = merged
        elif instance is None:
            required_keys = REQUIRED_SECRETS_BY_PROVIDER.get(rules_code, [])
            if required_keys:
                raise serializers.ValidationError(
                    {'secrets': ['Credentials are required when creating this provider.']}
                )

        return attrs

    def create(self, validated_data):
        secrets = validated_data.pop('secrets', {})
        validated_data['secrets_encrypted'] = encrypt_secret_payload(secrets)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        secrets = validated_data.pop('secrets', None)
        if secrets is not None:
            # validate() already merged incoming non-empty secrets with existing; encrypt that blob only.
            validated_data['secrets_encrypted'] = encrypt_secret_payload(secrets)
        return super().update(instance, validated_data)
