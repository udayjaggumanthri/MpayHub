"""
Serializers for contacts app.
"""
import re

from rest_framework import serializers
from apps.contacts.models import Contact
from apps.core.utils import validate_phone, validate_email


class ContactSerializer(serializers.ModelSerializer):
    """Serializer for Contact model."""

    class Meta:
        model = Contact
        fields = [
            'id',
            'name',
            'email',
            'phone',
            'contact_role',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        if value is None:
            raise serializers.ValidationError('Name is required.')
        s = str(value).strip()
        if len(s) < 2:
            raise serializers.ValidationError('Name must be at least 2 characters.')
        if len(s) > Contact._meta.get_field('name').max_length:
            raise serializers.ValidationError('Name is too long.')
        return s

    def validate_phone(self, value):
        if value is None:
            raise serializers.ValidationError('Phone is required.')
        digits = re.sub(r'\D', '', str(value))[:10]
        if not validate_phone(digits):
            raise serializers.ValidationError('Invalid phone number format (10 digits required).')
        return digits

    def validate_email(self, value):
        if value is None or not str(value).strip():
            raise serializers.ValidationError('Email address is required.')
        cleaned = str(value).strip()
        if not validate_email(cleaned):
            raise serializers.ValidationError('Invalid email format.')
        return cleaned

    def validate_contact_role(self, value):
        valid = {c[0] for c in Contact.ContactRole.choices}
        if value not in valid:
            raise serializers.ValidationError('Invalid contact role.')
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return attrs

        user = request.user
        phone = attrs.get('phone')
        if self.instance is not None:
            phone = attrs.get('phone', self.instance.phone)

        if phone is None:
            return attrs

        qs = Contact.objects.filter(user=user, phone=phone)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'phone': 'A contact with this phone number already exists.'}
            )
        return attrs
