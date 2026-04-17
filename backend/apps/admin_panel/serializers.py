"""
Serializers for admin_panel app.
"""
from decimal import Decimal

from rest_framework import serializers
from django.utils.text import slugify
from apps.admin_panel.models import Announcement, PaymentGateway, PayoutGateway, PayoutSlabConfig
from apps.fund_management.models import PayInPackage

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


class AnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for Announcement with optional image and flexible text."""

    image_url = serializers.SerializerMethodField(read_only=True)
    remove_image = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'message', 'image', 'image_url', 'remove_image',
            'priority', 'target_roles', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'image': {'write_only': True, 'required': False, 'allow_null': True},
        }

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        url = obj.image.url
        if request:
            return request.build_absolute_uri(url)
        return url

    def validate_image(self, value):
        if value and value.size > MAX_IMAGE_BYTES:
            raise serializers.ValidationError('Image must be 5 MB or smaller.')
        return value

    def validate_target_roles(self, value):
        if isinstance(value, str):
            import json
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError('Invalid JSON for target_roles.') from exc
        if not isinstance(value, list):
            raise serializers.ValidationError('target_roles must be a list.')
        if len(value) == 0:
            raise serializers.ValidationError('Select at least one target role.')
        return value

    def validate(self, data):
        instance = getattr(self, 'instance', None)
        remove = data.get('remove_image')
        if isinstance(remove, str):
            remove = remove.lower() in ('true', '1', 'yes')

        message = data.get('message', instance.message if instance else '') or ''
        message = message.strip()
        title = data.get('title', instance.title if instance else '') or ''
        title = title.strip()

        incoming_image = data.get('image')
        has_existing_image = bool(instance and instance.image) if instance else False
        if remove and instance and instance.image:
            has_existing_image = False

        if incoming_image:
            has_image = True
        elif has_existing_image:
            has_image = True
        else:
            has_image = False

        if not message and not has_image:
            raise serializers.ValidationError(
                {'non_field_errors': ['Provide a message, an image, or both.']}
            )

        # Persist stripped title/message (allow empty title when image or message exists)
        data['title'] = title
        data['message'] = message
        return data

    def create(self, validated_data):
        validated_data.pop('remove_image', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        remove = validated_data.pop('remove_image', False)
        if isinstance(remove, str):
            remove = remove.lower() in ('true', '1', 'yes')
        if remove and instance.image:
            instance.image.delete(save=False)
            validated_data['image'] = None
        return super().update(instance, validated_data)


class PaymentGatewaySerializer(serializers.ModelSerializer):
    """Serializer for PaymentGateway model."""
    api_master_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    visible_to_roles = serializers.JSONField(required=False, default=list)

    class Meta:
        model = PaymentGateway
        fields = [
            'id', 'name', 'charge_rate', 'status', 'visible_to_roles',
            'category', 'api_master', 'api_master_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        api_master = attrs.get('api_master')
        api_master_id = attrs.get('api_master_id')
        if api_master_id is not None:
            from apps.integrations.models import ApiMaster

            api_master = ApiMaster.objects.filter(id=api_master_id, is_deleted=False).first()
            if api_master_id and not api_master:
                raise serializers.ValidationError({'api_master_id': ['Invalid API Master id']})
            if api_master and api_master.provider_type != 'payments':
                raise serializers.ValidationError(
                    {'api_master_id': ['Selected API Master must be of provider_type=payments']}
                )
            attrs['api_master'] = api_master
        elif api_master and api_master.provider_type != 'payments':
            raise serializers.ValidationError(
                {'api_master': ['Selected API Master must be of provider_type=payments']}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('api_master_id', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('api_master_id', None)
        return super().update(instance, validated_data)


class PayoutGatewaySerializer(serializers.ModelSerializer):
    """Serializer for PayoutGateway model."""
    visible_to_roles = serializers.JSONField(required=False, default=list)

    class Meta:
        model = PayoutGateway
        fields = [
            'id', 'name', 'status', 'visible_to_roles',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PayInPackageAdminSerializer(serializers.ModelSerializer):
    """Admin serializer for dynamic pay-in commission profiles."""

    payment_gateway_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )
    total_deduction_pct = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PayInPackage
        fields = [
            'id',
            'code',
            'display_name',
            'provider',
            'payment_gateway',
            'payment_gateway_id',
            'min_amount',
            'max_amount_per_txn',
            'gateway_fee_pct',
            'admin_pct',
            'super_distributor_pct',
            'master_distributor_pct',
            'distributor_pct',
            'retailer_commission_pct',
            'total_deduction_pct',
            'is_active',
            'sort_order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'total_deduction_pct']

    def get_total_deduction_pct(self, obj):
        return (
            Decimal(str(obj.gateway_fee_pct))
            + Decimal(str(obj.admin_pct))
            + Decimal(str(obj.super_distributor_pct))
            + Decimal(str(obj.master_distributor_pct))
            + Decimal(str(obj.distributor_pct))
        )

    def validate_code(self, value):
        # Accept human-entered labels and normalize into a stable slug code.
        normalized = slugify(str(value or ''), allow_unicode=False)
        if not normalized:
            raise serializers.ValidationError('Code must contain letters or numbers.')
        return normalized

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = getattr(self, 'instance', None)
        provider = attrs.get('provider', getattr(instance, 'provider', 'mock'))
        payment_gateway = attrs.get('payment_gateway', getattr(instance, 'payment_gateway', None))
        payment_gateway_id = attrs.get('payment_gateway_id', None)
        if payment_gateway_id is not None:
            payment_gateway = PaymentGateway.objects.filter(id=payment_gateway_id).first()
            attrs['payment_gateway'] = payment_gateway
        if provider in ('razorpay', 'payu') and not payment_gateway:
            raise serializers.ValidationError(
                {'payment_gateway_id': ['Payment gateway is required for non-mock providers.']}
            )

        min_amount = attrs.get('min_amount', getattr(instance, 'min_amount', Decimal('0')))
        max_amount = attrs.get('max_amount_per_txn', getattr(instance, 'max_amount_per_txn', Decimal('0')))
        if Decimal(str(min_amount)) > Decimal(str(max_amount)):
            raise serializers.ValidationError(
                {'max_amount_per_txn': ['Max amount must be greater than or equal to min amount.']}
            )

        pct_fields = [
            'gateway_fee_pct',
            'admin_pct',
            'super_distributor_pct',
            'master_distributor_pct',
            'distributor_pct',
            'retailer_commission_pct',
        ]
        for field in pct_fields:
            val = Decimal(str(attrs.get(field, getattr(instance, field, Decimal('0')))))
            if val < 0:
                raise serializers.ValidationError({field: ['Percentage cannot be negative.']})
            if val > 100:
                raise serializers.ValidationError({field: ['Percentage cannot exceed 100.']})

        total_deduction = (
            Decimal(str(attrs.get('gateway_fee_pct', getattr(instance, 'gateway_fee_pct', Decimal('0')))))
            + Decimal(str(attrs.get('admin_pct', getattr(instance, 'admin_pct', Decimal('0')))))
            + Decimal(
                str(attrs.get('super_distributor_pct', getattr(instance, 'super_distributor_pct', Decimal('0'))))
            )
            + Decimal(
                str(attrs.get('master_distributor_pct', getattr(instance, 'master_distributor_pct', Decimal('0'))))
            )
            + Decimal(str(attrs.get('distributor_pct', getattr(instance, 'distributor_pct', Decimal('0')))))
        )
        if total_deduction <= 0:
            raise serializers.ValidationError(
                {'non_field_errors': ['Total deduction percentage must be greater than zero.']}
            )
        if total_deduction > 100:
            raise serializers.ValidationError(
                {'non_field_errors': ['Total deduction percentage cannot exceed 100%.']}
            )
        return attrs

    def create(self, validated_data):
        payment_gateway_id = validated_data.pop('payment_gateway_id', None)
        if payment_gateway_id:
            validated_data['payment_gateway'] = PaymentGateway.objects.filter(id=payment_gateway_id).first()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'payment_gateway_id' in validated_data:
            pg_id = validated_data.pop('payment_gateway_id')
            instance.payment_gateway = PaymentGateway.objects.filter(id=pg_id).first() if pg_id else None
        return super().update(instance, validated_data)


class PayoutSlabConfigSerializer(serializers.ModelSerializer):
    """Serializer for payout slab add-on charges."""

    class Meta:
        model = PayoutSlabConfig
        fields = [
            'id',
            'name',
            'low_max_amount',
            'low_charge',
            'high_charge',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = getattr(self, 'instance', None)
        low_max = Decimal(str(attrs.get('low_max_amount', getattr(instance, 'low_max_amount', Decimal('24999')))))
        low_c = Decimal(str(attrs.get('low_charge', getattr(instance, 'low_charge', Decimal('7')))))
        high_c = Decimal(str(attrs.get('high_charge', getattr(instance, 'high_charge', Decimal('15')))))
        if low_max < 0:
            raise serializers.ValidationError({'low_max_amount': ['Must be zero or positive.']})
        if low_c < 0:
            raise serializers.ValidationError({'low_charge': ['Must be zero or positive.']})
        if high_c < 0:
            raise serializers.ValidationError({'high_charge': ['Must be zero or positive.']})
        return attrs
