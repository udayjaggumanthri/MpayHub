"""
Serializers for admin_panel app.
"""
from rest_framework import serializers
from apps.admin_panel.models import Announcement, PaymentGateway, PayoutGateway

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

    class Meta:
        model = PaymentGateway
        fields = [
            'id', 'name', 'charge_rate', 'status', 'visible_to_roles',
            'category', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PayoutGatewaySerializer(serializers.ModelSerializer):
    """Serializer for PayoutGateway model."""

    class Meta:
        model = PayoutGateway
        fields = [
            'id', 'name', 'status', 'visible_to_roles',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
