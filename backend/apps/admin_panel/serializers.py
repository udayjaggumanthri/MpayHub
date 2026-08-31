"""
Serializers for admin_panel app.
"""
from decimal import Decimal

from rest_framework import serializers
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify
from apps.admin_panel.models import Announcement, PaymentGateway, PayoutGateway, PayoutSlabConfig, SmtpConfig
from apps.fund_management.models import PayInPackage, PayInQrAccount, PayoutSlabTier

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
}


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
        if not value:
            return value
        if value.size > MAX_IMAGE_BYTES:
            raise serializers.ValidationError('Image must be 5 MB or smaller.')
        if isinstance(value, UploadedFile):
            ct = str(getattr(value, 'content_type', '') or '').lower()
            if ct and ct not in ALLOWED_IMAGE_CONTENT_TYPES:
                raise serializers.ValidationError('Unsupported image type. Upload JPG, PNG, WEBP, or GIF.')
        # Verify file is a real image (prevents polyglots / fake extensions).
        try:
            from PIL import Image

            pos = value.tell() if hasattr(value, 'tell') else None
            img = Image.open(value)
            img.verify()
            if pos is not None and hasattr(value, 'seek'):
                value.seek(pos)
        except Exception:
            raise serializers.ValidationError('Invalid or corrupted image.')
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


class PayoutSlabTierSerializer(serializers.ModelSerializer):
    """Per-package payout slab row (flat charge for amount band)."""

    class Meta:
        model = PayoutSlabTier
        fields = ['id', 'sort_order', 'min_amount', 'max_amount', 'flat_charge']
        read_only_fields = ['id']


def _validate_payout_slabs_list(slabs):
    """Ensure tiers cover from 0, are ordered, contiguous, and only the last may be open-ended."""
    if slabs is None:
        return
    if len(slabs) == 0:
        return
    step = Decimal('0.0001')
    rows = []
    for i, raw in enumerate(slabs):
        lo = Decimal(str(raw['min_amount']))
        hi_raw = raw.get('max_amount', None)
        if hi_raw in (None, ''):
            hi = None
        else:
            hi = Decimal(str(hi_raw))
        fc = Decimal(str(raw['flat_charge']))
        so = int(raw.get('sort_order', i))
        if fc < 0:
            raise serializers.ValidationError({'payout_slabs': ['flat_charge cannot be negative.']})
        if hi is not None and hi < lo:
            raise serializers.ValidationError({'payout_slabs': ['max_amount must be >= min_amount per tier.']})
        rows.append({'sort_order': so, 'min_amount': lo, 'max_amount': hi, 'flat_charge': fc})

    rows.sort(key=lambda r: (r['sort_order'], r['min_amount']))
    if rows[0]['min_amount'] != Decimal('0'):
        raise serializers.ValidationError(
            {'payout_slabs': ['First tier must have min_amount 0.']}
        )
    for i in range(len(rows) - 1):
        if rows[i]['max_amount'] is None:
            raise serializers.ValidationError(
                {'payout_slabs': ['Only the last tier may omit max_amount (open-ended).']}
            )
    for i in range(len(rows) - 1):
        prev_hi = rows[i]['max_amount']
        next_lo = rows[i + 1]['min_amount']
        if next_lo != prev_hi + step:
            raise serializers.ValidationError(
                {
                    'payout_slabs': [
                        f'Tiers must be contiguous (step {step}): after max {prev_hi} expect min {prev_hi + step}, got {next_lo}.'
                    ]
                }
            )


def _sync_payout_slabs(package, slabs):
    """Replace all payout tiers for a package (hard delete children)."""
    PayoutSlabTier.objects.filter(package=package).delete()
    if not slabs:
        return
    for i, row in enumerate(slabs):
        PayoutSlabTier.objects.create(
            package=package,
            sort_order=int(row.get('sort_order', i)),
            min_amount=Decimal(str(row['min_amount'])),
            max_amount=Decimal(str(row['max_amount'])) if row.get('max_amount') not in (None, '') else None,
            flat_charge=Decimal(str(row['flat_charge'])),
        )


def _parse_rail_fee(value):
    if value is None or value == '':
        return None
    return Decimal(str(value))


def _gateway_specs_from_initial(initial: dict, gateway_ids: list[int] | None) -> list[dict]:
    if isinstance(initial, dict) and initial.get('package_gateways_input'):
        specs = []
        for row in initial.get('package_gateways_input') or []:
            if not isinstance(row, dict):
                continue
            gid = row.get('payment_gateway_id') or row.get('id')
            if gid is None:
                continue
            specs.append(
                {
                    'payment_gateway_id': int(gid),
                    'gateway_fee_pct': _parse_rail_fee(row.get('gateway_fee_pct')),
                }
            )
        return specs
    if isinstance(initial, dict) and initial.get('package_gateways'):
        specs = []
        for row in initial.get('package_gateways') or []:
            if not isinstance(row, dict):
                continue
            gid = row.get('payment_gateway_id') or row.get('id')
            if gid is None:
                continue
            specs.append(
                {
                    'payment_gateway_id': int(gid),
                    'gateway_fee_pct': _parse_rail_fee(row.get('gateway_fee_pct')),
                }
            )
        return specs
    return [
        {'payment_gateway_id': int(gid), 'gateway_fee_pct': None}
        for gid in (gateway_ids or [])
    ]


def _qr_specs_from_initial(initial: dict, qr_ids: list[int] | None) -> list[dict]:
    if isinstance(initial, dict) and initial.get('package_qr_accounts_input'):
        specs = []
        for row in initial.get('package_qr_accounts_input') or []:
            if not isinstance(row, dict):
                continue
            qid = row.get('qr_account_id') or row.get('id')
            if qid is None:
                continue
            specs.append(
                {
                    'qr_account_id': int(qid),
                    'gateway_fee_pct': _parse_rail_fee(row.get('gateway_fee_pct')),
                }
            )
        return specs
    if isinstance(initial, dict) and initial.get('package_qr_accounts'):
        specs = []
        for row in initial.get('package_qr_accounts') or []:
            if not isinstance(row, dict):
                continue
            qid = row.get('qr_account_id') or row.get('id')
            if qid is None:
                continue
            specs.append(
                {
                    'qr_account_id': int(qid),
                    'gateway_fee_pct': _parse_rail_fee(row.get('gateway_fee_pct')),
                }
            )
        return specs
    return [
        {'qr_account_id': int(qid), 'gateway_fee_pct': None}
        for qid in (qr_ids or [])
    ]


class PayInPackageAdminSerializer(serializers.ModelSerializer):
    """Admin serializer for dynamic pay-in commission profiles."""

    payment_gateway_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )
    payment_gateway_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    default_payment_gateway_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True,
    )
    package_gateways = serializers.SerializerMethodField(read_only=True)
    package_gateways_input = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
    )
    qr_account_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    default_qr_account_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True,
    )
    package_qr_accounts = serializers.SerializerMethodField(read_only=True)
    package_qr_accounts_input = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
    )
    total_deduction_pct = serializers.SerializerMethodField(read_only=True)
    max_rail_gateway_fee_pct = serializers.SerializerMethodField(read_only=True)
    payout_slabs = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PayInPackage
        fields = [
            'id',
            'code',
            'display_name',
            'provider',
            'payment_gateway',
            'payment_gateway_id',
            'payment_gateway_ids',
            'default_payment_gateway_id',
            'package_gateways',
            'package_gateways_input',
            'qr_account_ids',
            'default_qr_account_id',
            'package_qr_accounts',
            'package_qr_accounts_input',
            'min_amount',
            'max_amount_per_txn',
            'gateway_fee_pct',
            'max_rail_gateway_fee_pct',
            'admin_pct',
            'super_distributor_pct',
            'master_distributor_pct',
            'distributor_pct',
            'retailer_commission_pct',
            'total_deduction_pct',
            'is_active',
            'is_default',
            'sort_order',
            'payout_slabs',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'total_deduction_pct',
            'max_rail_gateway_fee_pct',
            'gateway_fee_pct',
            'provider',
        ]

    def get_payout_slabs(self, obj):
        qs = obj.payout_slabs.filter(is_deleted=False).order_by('sort_order', 'min_amount')
        return PayoutSlabTierSerializer(qs, many=True).data

    def get_package_gateways(self, obj):
        from apps.fund_management.package_gateways import serialize_package_gateways

        return serialize_package_gateways(obj)

    def get_package_qr_accounts(self, obj):
        from apps.fund_management.package_qr_accounts import serialize_package_qr_accounts

        return serialize_package_qr_accounts(obj)

    def get_max_rail_gateway_fee_pct(self, obj):
        from apps.fund_management.rail_fees import max_package_gateway_fee_pct

        return max_package_gateway_fee_pct(obj)

    def get_total_deduction_pct(self, obj):
        from apps.fund_management.rail_fees import max_package_gateway_fee_pct

        gw = max_package_gateway_fee_pct(obj)
        return (
            gw
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
        payment_gateway = attrs.get('payment_gateway', getattr(instance, 'payment_gateway', None))
        payment_gateway_id = attrs.get('payment_gateway_id', None)
        if payment_gateway_id is not None:
            payment_gateway = PaymentGateway.objects.filter(id=payment_gateway_id).first()
            attrs['payment_gateway'] = payment_gateway
        gateway_ids = attrs.get('payment_gateway_ids')
        initial = getattr(self, 'initial_data', None) or {}
        if gateway_ids is None and isinstance(initial, dict) and 'payment_gateway_ids' in initial:
            gateway_ids = initial.get('payment_gateway_ids')
        gateway_ids = initial.get('payment_gateway_ids')
        qr_ids = attrs.get('qr_account_ids')
        if qr_ids is None and isinstance(initial, dict) and 'qr_account_ids' in initial:
            qr_ids = initial.get('qr_account_ids')

        gw_specs = _gateway_specs_from_initial(initial if isinstance(initial, dict) else {}, gateway_ids)
        qr_specs = _qr_specs_from_initial(initial if isinstance(initial, dict) else {}, qr_ids)

        has_gw = bool(gw_specs) or bool(payment_gateway)
        if instance and not has_gw:
            has_gw = instance.package_gateways.filter(is_deleted=False).exists()
        has_qr = bool(qr_specs)
        if instance and not has_qr:
            has_qr = instance.package_qr_links.filter(is_deleted=False).exists()

        if gateway_ids is not None and len(gateway_ids) == 0 and not gw_specs:
            has_gw = False
        if qr_ids is not None and len(qr_ids) == 0 and not qr_specs:
            has_qr = False

        if not has_gw and not has_qr:
            raise serializers.ValidationError(
                {
                    'non_field_errors': [
                        'Link at least one payment gateway or one QR account to this package.'
                    ]
                }
            )

        min_amount = attrs.get('min_amount', getattr(instance, 'min_amount', Decimal('0')))
        max_amount = attrs.get('max_amount_per_txn', getattr(instance, 'max_amount_per_txn', Decimal('0')))
        if Decimal(str(min_amount)) > Decimal(str(max_amount)):
            raise serializers.ValidationError(
                {'max_amount_per_txn': ['Max amount must be greater than or equal to min amount.']}
            )

        pct_fields = [
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

        admin_pct = Decimal(str(attrs.get('admin_pct', getattr(instance, 'admin_pct', Decimal('0')))))
        sd_pct = Decimal(str(attrs.get('super_distributor_pct', getattr(instance, 'super_distributor_pct', Decimal('0')))))
        md_pct = Decimal(str(attrs.get('master_distributor_pct', getattr(instance, 'master_distributor_pct', Decimal('0')))))
        d_pct = Decimal(str(attrs.get('distributor_pct', getattr(instance, 'distributor_pct', Decimal('0')))))

        from apps.fund_management.models import PayInPackage as PayInPackageModel
        from apps.fund_management.rail_fees import (
            effective_link_fee,
            gateway_floor_pct,
            qr_floor_pct,
            validate_package_rail_fees,
        )

        max_gw_fee = Decimal('0')
        for spec in gw_specs:
            gid = int(spec['payment_gateway_id'])
            gw = PaymentGateway.objects.filter(pk=gid).first()
            if not gw:
                continue
            link_fee = spec.get('gateway_fee_pct')
            if link_fee is not None and link_fee != '':
                fee = Decimal(str(link_fee))
            else:
                fee = gateway_floor_pct(gw)
            max_gw_fee = max(max_gw_fee, fee)

        for spec in qr_specs:
            qid = int(spec['qr_account_id'])
            qr = PayInQrAccount.objects.filter(pk=qid).first()
            if not qr:
                continue
            link_fee = spec.get('gateway_fee_pct')
            if link_fee is not None and link_fee != '':
                fee = Decimal(str(link_fee))
            else:
                fee = qr_floor_pct(qr)
            max_gw_fee = max(max_gw_fee, fee)

        if not gw_specs and not qr_specs and instance:
            from apps.fund_management.rail_fees import max_package_gateway_fee_pct

            max_gw_fee = max_package_gateway_fee_pct(instance)
        elif not gw_specs and not qr_specs:
            max_gw_fee = Decimal(
                str(getattr(instance, 'gateway_fee_pct', Decimal('0')) if instance else Decimal('0'))
            )

        attrs['gateway_fee_pct'] = max_gw_fee

        pkg_stub = instance or PayInPackageModel(
            gateway_fee_pct=max_gw_fee,
            admin_pct=admin_pct,
            super_distributor_pct=sd_pct,
            master_distributor_pct=md_pct,
            distributor_pct=d_pct,
        )
        if instance:
            pkg_stub.gateway_fee_pct = max_gw_fee

        rail_errors = validate_package_rail_fees(pkg_stub, gw_specs, qr_specs)
        if rail_errors:
            raise serializers.ValidationError({'package_gateways': rail_errors})

        attrs['gateway_fee_pct'] = max_gw_fee

        total_deduction = max_gw_fee + admin_pct + sd_pct + md_pct + d_pct
        if total_deduction <= 0:
            raise serializers.ValidationError(
                {'non_field_errors': ['Total deduction percentage must be greater than zero.']}
            )
        if total_deduction > 100:
            raise serializers.ValidationError(
                {'non_field_errors': ['Total deduction percentage cannot exceed 100%.']}
            )

        if isinstance(initial, dict) and 'payout_slabs' in initial:
            _validate_payout_slabs_list(initial.get('payout_slabs'))

        return attrs

    def create(self, validated_data):
        from apps.fund_management.package_gateways import sync_package_gateway_links
        from apps.fund_management.rail_fees import derive_provider_from_gateway

        validated_data.pop('package_gateways_input', None)
        validated_data.pop('package_qr_accounts_input', None)
        gateway_ids = validated_data.pop('payment_gateway_ids', None)
        default_gateway_id = validated_data.pop('default_payment_gateway_id', None)
        payment_gateway_id = validated_data.pop('payment_gateway_id', None)
        qr_ids = validated_data.pop('qr_account_ids', None)
        default_qr_id = validated_data.pop('default_qr_account_id', None)

        if gateway_ids:
            primary_id = default_gateway_id or gateway_ids[0]
            primary_gw = PaymentGateway.objects.filter(id=primary_id).first()
            validated_data['payment_gateway'] = primary_gw
            validated_data['provider'] = derive_provider_from_gateway(primary_gw)
        elif payment_gateway_id:
            primary_gw = PaymentGateway.objects.filter(id=payment_gateway_id).first()
            validated_data['payment_gateway'] = primary_gw
            validated_data['provider'] = derive_provider_from_gateway(primary_gw)

        validated_data['retailer_commission_pct'] = Decimal('0')
        instance = super().create(validated_data)

        initial = getattr(self, 'initial_data', None) or {}
        gw_specs = _gateway_specs_from_initial(initial if isinstance(initial, dict) else {}, gateway_ids)
        qr_specs = _qr_specs_from_initial(initial if isinstance(initial, dict) else {}, qr_ids)
        gw_fee_map = {s['payment_gateway_id']: s.get('gateway_fee_pct') for s in gw_specs}
        qr_fee_map = {s['qr_account_id']: s.get('gateway_fee_pct') for s in qr_specs}

        if gateway_ids is not None:
            sync_package_gateway_links(
                instance,
                gateway_ids,
                default_gateway_id=default_gateway_id,
                gateway_fees=gw_fee_map,
            )
        elif instance.payment_gateway_id:
            sync_package_gateway_links(
                instance,
                [instance.payment_gateway_id],
                default_gateway_id=default_gateway_id or instance.payment_gateway_id,
                gateway_fees=gw_fee_map,
            )
        if isinstance(initial, dict) and 'payout_slabs' in initial:
            _sync_payout_slabs(instance, initial.get('payout_slabs') or [])
        if qr_ids is not None:
            from apps.fund_management.package_qr_accounts import sync_package_qr_links

            sync_package_qr_links(
                instance, qr_ids, default_qr_account_id=default_qr_id, qr_fees=qr_fee_map
            )
        return instance

    def update(self, instance, validated_data):
        from apps.fund_management.package_gateways import sync_package_gateway_links
        from apps.fund_management.rail_fees import derive_provider_from_gateway

        validated_data.pop('package_gateways_input', None)
        validated_data.pop('package_qr_accounts_input', None)
        gateway_ids = validated_data.pop('payment_gateway_ids', None)
        default_gateway_id = validated_data.pop('default_payment_gateway_id', None)
        qr_ids = validated_data.pop('qr_account_ids', None)
        default_qr_id = validated_data.pop('default_qr_account_id', None)

        if 'payment_gateway_id' in validated_data:
            pg_id = validated_data.pop('payment_gateway_id')
            validated_data['payment_gateway'] = (
                PaymentGateway.objects.filter(id=pg_id).first() if pg_id else None
            )
        if gateway_ids is not None:
            primary_id = default_gateway_id or (gateway_ids[0] if gateway_ids else None)
            if primary_id:
                primary_gw = PaymentGateway.objects.filter(id=primary_id).first()
                validated_data['payment_gateway'] = primary_gw
                validated_data['provider'] = derive_provider_from_gateway(primary_gw)
        elif validated_data.get('payment_gateway'):
            validated_data['provider'] = derive_provider_from_gateway(validated_data['payment_gateway'])

        validated_data['retailer_commission_pct'] = Decimal('0')
        instance = super().update(instance, validated_data)

        initial = getattr(self, 'initial_data', None) or {}
        gw_specs = _gateway_specs_from_initial(initial if isinstance(initial, dict) else {}, gateway_ids)
        qr_specs = _qr_specs_from_initial(initial if isinstance(initial, dict) else {}, qr_ids)
        gw_fee_map = {s['payment_gateway_id']: s.get('gateway_fee_pct') for s in gw_specs}
        qr_fee_map = {s['qr_account_id']: s.get('gateway_fee_pct') for s in qr_specs}

        if gateway_ids is not None:
            sync_package_gateway_links(
                instance,
                gateway_ids,
                default_gateway_id=default_gateway_id,
                gateway_fees=gw_fee_map,
            )
        if isinstance(initial, dict) and 'payout_slabs' in initial:
            _sync_payout_slabs(instance, initial.get('payout_slabs') or [])
        if qr_ids is not None:
            from apps.fund_management.package_qr_accounts import sync_package_qr_links

            sync_package_qr_links(
                instance, qr_ids, default_qr_account_id=default_qr_id, qr_fees=qr_fee_map
            )
        return instance


class PayInPackageListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for paginated package list."""

    total_deduction_pct = serializers.SerializerMethodField(read_only=True)
    max_rail_gateway_fee_pct = serializers.SerializerMethodField(read_only=True)
    gateway_count = serializers.SerializerMethodField(read_only=True)
    qr_count = serializers.SerializerMethodField(read_only=True)
    default_gateway_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PayInPackage
        fields = [
            'id',
            'code',
            'display_name',
            'provider',
            'min_amount',
            'max_amount_per_txn',
            'max_rail_gateway_fee_pct',
            'admin_pct',
            'super_distributor_pct',
            'master_distributor_pct',
            'distributor_pct',
            'total_deduction_pct',
            'gateway_count',
            'qr_count',
            'default_gateway_name',
            'is_active',
            'is_default',
            'sort_order',
            'payout_slabs',
        ]
        read_only_fields = fields

    def get_payout_slabs(self, obj):
        return obj.payout_slabs.filter(is_deleted=False).count()

    def get_max_rail_gateway_fee_pct(self, obj):
        from apps.fund_management.rail_fees import max_package_gateway_fee_pct

        return max_package_gateway_fee_pct(obj)

    def get_total_deduction_pct(self, obj):
        from apps.fund_management.rail_fees import max_package_gateway_fee_pct

        gw = max_package_gateway_fee_pct(obj)
        return (
            gw
            + Decimal(str(obj.admin_pct))
            + Decimal(str(obj.super_distributor_pct))
            + Decimal(str(obj.master_distributor_pct))
            + Decimal(str(obj.distributor_pct))
        )

    def get_gateway_count(self, obj):
        return obj.package_gateways.filter(is_deleted=False, is_active=True).count()

    def get_qr_count(self, obj):
        return obj.package_qr_links.filter(is_deleted=False, is_active=True).count()

    def get_default_gateway_name(self, obj):
        link = (
            obj.package_gateways.filter(is_deleted=False, is_active=True, is_default=True)
            .select_related('payment_gateway')
            .first()
        )
        if link and link.payment_gateway:
            return link.payment_gateway.name
        if obj.payment_gateway:
            return obj.payment_gateway.name
        return obj.provider or '—'


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


class SmtpConfigSerializer(serializers.ModelSerializer):
    """SMTP config for admin UI; password never returned."""

    has_password = serializers.SerializerMethodField()

    class Meta:
        model = SmtpConfig
        fields = [
            'id',
            'name',
            'host',
            'port',
            'use_tls',
            'use_ssl',
            'username',
            'from_email',
            'enabled',
            'is_active',
            'created_at',
            'updated_at',
            'has_password',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'has_password']

    def get_has_password(self, obj) -> bool:
        return bool((getattr(obj, 'password_encrypted', None) or '').strip())

    def validate_name(self, value):
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('Profile name is required.')
        qs = SmtpConfig.objects.filter(is_deleted=False, name=name)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A profile with this name already exists.')
        return name

    def validate(self, attrs):
        attrs = super().validate(attrs)
        use_tls = bool(attrs.get('use_tls', getattr(self.instance, 'use_tls', True)))
        use_ssl = bool(attrs.get('use_ssl', getattr(self.instance, 'use_ssl', False)))
        if use_tls and use_ssl:
            raise serializers.ValidationError(
                {'use_ssl': ['Enable either TLS (587) or SSL (465), not both.']}
            )
        port = int(attrs.get('port', getattr(self.instance, 'port', 587)) or 587)
        if port == 465 and use_tls and not use_ssl:
            raise serializers.ValidationError(
                {'use_ssl': ['Port 465 typically requires SSL (use_ssl=true, use_tls=false).']}
            )
        if port == 587 and use_ssl and not use_tls:
            raise serializers.ValidationError(
                {'use_tls': ['Port 587 typically requires TLS (use_tls=true, use_ssl=false).']}
            )
        enabled = bool(attrs.get('enabled', getattr(self.instance, 'enabled', False)))
        is_active = bool(attrs.get('is_active', getattr(self.instance, 'is_active', False)))
        if (enabled or is_active) and not str(attrs.get('from_email', getattr(self.instance, 'from_email', '')) or '').strip():
            raise serializers.ValidationError({'from_email': ['From email is required when SMTP is enabled.']})
        return attrs


class SmtpSecretUpdateSerializer(serializers.Serializer):
    password = serializers.CharField(required=False, allow_blank=True)


class SmtpTestEmailSerializer(serializers.Serializer):
    to_email = serializers.EmailField(required=False, allow_blank=True)


class SmsProviderConfigSerializer(serializers.ModelSerializer):
    has_auth_key = serializers.SerializerMethodField()

    class Meta:
        from apps.notifications.models import SmsProviderConfig

        model = SmsProviderConfig
        fields = [
            'id',
            'name',
            'provider',
            'sender_id',
            'enabled',
            'is_active',
            'api_base_url',
            'route',
            'country_code',
            'last_test_at',
            'last_test_status',
            'last_test_error',
            'created_at',
            'updated_at',
            'has_auth_key',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'has_auth_key',
            'last_test_at',
            'last_test_status',
            'last_test_error',
        ]

    def get_has_auth_key(self, obj) -> bool:
        return bool((getattr(obj, 'auth_key_encrypted', None) or '').strip())

    def validate_name(self, value):
        from apps.notifications.models import SmsProviderConfig

        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('Profile name is required.')
        qs = SmsProviderConfig.objects.filter(is_deleted=False, name=name)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A profile with this name already exists.')
        return name

    def validate_provider(self, value):
        # New profiles are MSG91-only; console is legacy and not offered in Admin UI.
        provider = (value or 'msg91').strip().lower()
        if provider not in ('msg91', 'console'):
            raise serializers.ValidationError('Unsupported SMS provider.')
        if not self.instance and provider == 'console':
            raise serializers.ValidationError('Use MSG91 for new SMS profiles.')
        return provider

    def validate_sender_id(self, value):
        sender = (value or '').strip()
        if not sender:
            raise serializers.ValidationError('DLT Sender ID is required.')
        return sender


class SmsSecretUpdateSerializer(serializers.Serializer):
    auth_key = serializers.CharField(required=False, allow_blank=True)


class SmsTestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    template_id = serializers.CharField(required=False, allow_blank=True)
    variables = serializers.JSONField(required=False)


class SmsTemplateUpdateSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField(required=False)
    template_id = serializers.CharField(required=False, allow_blank=True)
    sample_variables = serializers.JSONField(required=False)
    variable_map = serializers.JSONField(required=False)

    def validate_variable_map(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('variable_map must be an object.')
        cleaned = {}
        for app_key, msg91_key in value.items():
            ak = str(app_key or '').strip()
            mk = str(msg91_key or '').strip()
            if not ak:
                continue
            if mk and not mk.lower().startswith('var'):
                # Allow any MSG91 key but prefer varN; still accept explicit names
                pass
            cleaned[ak] = mk
        return cleaned


class SmsTemplateTestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    variables = serializers.JSONField(required=False)


class SmsTemplateFetchSerializer(serializers.Serializer):
    template_id = serializers.CharField(required=False, allow_blank=True)


class SmsDeliveryLogSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.notifications.models import SmsDeliveryLog

        model = SmsDeliveryLog
        fields = [
            'id',
            'event_key',
            'phone_masked',
            'template_id',
            'status',
            'skip_reason',
            'provider_message_id',
            'error_message',
            'context_json',
            'created_at',
        ]
        read_only_fields = fields


class EmailNotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.notifications.models import EmailNotificationTemplate

        model = EmailNotificationTemplate
        fields = [
            'id',
            'event_key',
            'module',
            'label',
            'description',
            'is_enabled',
            'subject_template',
            'body_html_template',
            'body_plain_template',
            'variable_schema',
            'sample_variables',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'event_key', 'module', 'label', 'description', 'variable_schema', 'created_at', 'updated_at']


class EmailTemplateUpdateSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField(required=False)
    subject_template = serializers.CharField(required=False, allow_blank=True, max_length=255)
    body_html_template = serializers.CharField(required=False, allow_blank=True)
    body_plain_template = serializers.CharField(required=False, allow_blank=True)
    sample_variables = serializers.JSONField(required=False)


class EmailTemplateTestSerializer(serializers.Serializer):
    to_email = serializers.EmailField(required=False, allow_blank=True)
    variables = serializers.JSONField(required=False)
