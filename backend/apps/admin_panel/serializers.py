"""
Serializers for admin_panel app.
"""
from rest_framework import serializers
from apps.admin_panel.models import Announcement, PaymentGateway, PayoutGateway


class AnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for Announcement model."""
    
    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'message', 'priority', 'target_roles',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


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
