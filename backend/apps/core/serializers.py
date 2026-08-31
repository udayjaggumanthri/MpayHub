"""Serializers for core app."""
from django.core.files.uploadedfile import UploadedFile
from rest_framework import serializers

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
}


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ('true', '1', 'yes', 'on')


class SystemMaintenanceUpdateSerializer(serializers.Serializer):
    """Admin PATCH body for maintenance config."""

    pay_in_enabled = serializers.BooleanField(required=False)
    payout_enabled = serializers.BooleanField(required=False)
    bbps_enabled = serializers.BooleanField(required=False)
    aeps_enabled = serializers.BooleanField(required=False)
    pay_in_message = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    payout_message = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    bbps_message = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    aeps_message = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    reason_internal = serializers.CharField(required=False, allow_blank=True, max_length=5000)


class PlatformAppearanceUpdateSerializer(serializers.Serializer):
    """Admin PATCH body for platform appearance config."""

    site_title = serializers.CharField(required=False, allow_blank=True, max_length=120)
    login_welcome_heading = serializers.CharField(required=False, allow_blank=True, max_length=200)
    login_tagline = serializers.CharField(required=False, allow_blank=True, max_length=300)
    login_footer_note = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    login_footer_privacy_url = serializers.URLField(required=False, allow_blank=True, max_length=500)
    login_footer_terms_url = serializers.URLField(required=False, allow_blank=True, max_length=500)
    login_footer_refund_url = serializers.URLField(required=False, allow_blank=True, max_length=500)
    default_theme = serializers.ChoiceField(required=False, choices=['light', 'dark'])
    user_theme_toggle_enabled = serializers.BooleanField(required=False)
    logo = serializers.ImageField(required=False, allow_null=True)
    remove_logo = serializers.BooleanField(required=False, default=False)

    def validate_user_theme_toggle_enabled(self, value):
        return _coerce_bool(value)

    def validate_remove_logo(self, value):
        return _coerce_bool(value)

    def validate_logo(self, value):
        if not value:
            return value
        if value.size > MAX_IMAGE_BYTES:
            raise serializers.ValidationError('Image must be 5 MB or smaller.')
        if isinstance(value, UploadedFile):
            ct = str(getattr(value, 'content_type', '') or '').lower()
            if ct and ct not in ALLOWED_IMAGE_CONTENT_TYPES:
                raise serializers.ValidationError('Unsupported image type. Upload JPG, PNG, WEBP, or GIF.')
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
