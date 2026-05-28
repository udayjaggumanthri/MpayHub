"""Serializers for core app."""
from rest_framework import serializers


class SystemMaintenanceUpdateSerializer(serializers.Serializer):
    """Admin PATCH body for maintenance config."""

    pay_in_enabled = serializers.BooleanField(required=False)
    payout_enabled = serializers.BooleanField(required=False)
    bbps_enabled = serializers.BooleanField(required=False)
    pay_in_message = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    payout_message = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    bbps_message = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    reason_internal = serializers.CharField(required=False, allow_blank=True, max_length=5000)
