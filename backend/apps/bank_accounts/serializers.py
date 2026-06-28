"""
Serializers for bank_accounts app.
"""
from rest_framework import serializers

from apps.bank_accounts.models import BankAccount
from apps.bank_accounts.services import consume_validation_token
from apps.core.exceptions import BankValidationFailed
from apps.core.utils import validate_ifsc, validate_phone


class BankAccountSerializer(serializers.ModelSerializer):
    """Serializer for BankAccount model."""

    validation_token = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = BankAccount
        fields = [
            'id', 'contact', 'account_number', 'ifsc', 'bank_name',
            'account_holder_name', 'beneficiary_name', 'mobile_number', 'is_verified',
            'verification_reference_id', 'provider_code', 'branch', 'city',
            'name_match_score', 'name_match_result', 'verification_details',
            'verified_at', 'validation_token', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'beneficiary_name', 'is_verified', 'verification_reference_id',
            'provider_code', 'branch', 'city', 'name_match_score', 'name_match_result',
            'verification_details', 'verified_at', 'created_at', 'updated_at',
        ]

    def validate_ifsc(self, value):
        """Validate IFSC code."""
        if not validate_ifsc(value):
            raise serializers.ValidationError('Invalid IFSC code format.')
        return value.upper()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is not None:
            attrs.pop('validation_token', None)
            return attrs

        request = self.context.get('request')
        user = getattr(request, 'user', None)
        token = str(attrs.get('validation_token') or '').strip()
        account_number = attrs.get('account_number', '')
        ifsc = attrs.get('ifsc', '')

        if user is not None and token:
            try:
                attempt = consume_validation_token(
                    user,
                    validation_token=token,
                    account_number=account_number,
                    ifsc=ifsc,
                )
            except BankValidationFailed as exc:
                raise serializers.ValidationError({'validation_token': [str(exc)]}) from exc

            if attempt.bank_account_id:
                self._existing_verified_account = attempt.bank_account
                return attrs

            response_meta = attempt.response_meta if isinstance(attempt.response_meta, dict) else {}
            beneficiary = str(response_meta.get('beneficiary_name') or response_meta.get('name_at_bank') or '').strip()
            if beneficiary:
                attrs['beneficiary_name'] = beneficiary
                attrs['account_holder_name'] = attrs.get('account_holder_name') or beneficiary
            bank_name = str(response_meta.get('bank_name') or attrs.get('bank_name') or '').strip()
            if bank_name:
                attrs['bank_name'] = bank_name
            attrs['is_verified'] = True
            attrs['verification_reference_id'] = str(response_meta.get('reference_id') or attempt.reference_id or '')
            attrs['branch'] = str(response_meta.get('branch') or '')
            attrs['city'] = str(response_meta.get('city') or '')
            attrs['name_match_score'] = str(response_meta.get('name_match_score') or '')
            attrs['name_match_result'] = str(response_meta.get('name_match_result') or '')
            attrs['verification_details'] = response_meta
            attrs['provider_code'] = attempt.provider_code
            if not attrs.get('verified_at'):
                from django.utils import timezone
                attrs['verified_at'] = timezone.now()
        elif not token:
            existing = BankAccount.objects.filter(
                user=user,
                account_number=account_number,
                ifsc=ifsc,
                is_verified=True,
                is_deleted=False,
            ).first()
            if existing is not None:
                self._existing_verified_account = existing
                return attrs
            raise serializers.ValidationError(
                {'validation_token': ['Bank account must be validated before saving.']}
            )
        return attrs

    def create(self, validated_data):
        existing = getattr(self, '_existing_verified_account', None)
        validated_data.pop('validation_token', None)
        if existing is not None:
            return existing
        return super().create(validated_data)


class BankAccountValidationSerializer(serializers.Serializer):
    """Serializer for bank account validation."""
    account_number = serializers.CharField(max_length=20)
    ifsc = serializers.CharField(max_length=11)
    mobile_number = serializers.CharField(max_length=10)

    def validate_ifsc(self, value):
        """Validate IFSC code."""
        if not validate_ifsc(value):
            raise serializers.ValidationError('Invalid IFSC code format.')
        return value.upper()

    def validate_mobile_number(self, value):
        mobile = str(value or '').strip()
        if not validate_phone(mobile):
            raise serializers.ValidationError('Enter a valid 10-digit mobile number.')
        return mobile
