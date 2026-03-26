"""
Serializers for contacts app.
"""
from rest_framework import serializers
from apps.contacts.models import Contact
from apps.core.utils import validate_phone, validate_email


class ContactSerializer(serializers.ModelSerializer):
    """Serializer for Contact model."""
    
    class Meta:
        model = Contact
        fields = ['id', 'name', 'email', 'phone', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_phone(self, value):
        """Validate phone number."""
        if not validate_phone(value):
            raise serializers.ValidationError("Invalid phone number format.")
        return value
    
    def validate_email(self, value):
        """Validate email."""
        if value and not validate_email(value):
            raise serializers.ValidationError("Invalid email format.")
        return value
