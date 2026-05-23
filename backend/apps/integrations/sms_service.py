"""
SMS service integration — thin backward-compatible wrapper around SmsNotificationService.
"""
from django.conf import settings

from apps.integrations.base import BaseIntegration
from apps.notifications.catalog import AUTH_OTP_PURPOSE_TO_EVENT
from apps.notifications.services.dispatch import SmsNotificationService


class SMSService(BaseIntegration):
    """
    Legacy SMS entry point; delegates OTP sends to admin-configured MSG91 dispatch.
    """

    def __init__(self):
        self.provider = getattr(settings, 'SMS_PROVIDER', 'console')
        super().__init__()

    def _load_config(self):
        pass

    def is_available(self):
        if settings.DEBUG:
            return True
        from apps.notifications.models import SmsProviderConfig

        cfg = SmsProviderConfig.objects.filter(is_deleted=False, is_active=True, enabled=True).first()
        return bool(cfg)

    def handle_error(self, error):
        print(f'SMS Service Error: {error}')

    def send_otp(self, phone, otp_code, purpose='password-reset'):
        event_key = AUTH_OTP_PURPOSE_TO_EVENT.get(purpose)
        if not event_key:
            if settings.DEBUG:
                print(f'[SMS] OTP for {phone}: {otp_code} (Purpose: {purpose})')
            return
        SmsNotificationService.dispatch(
            event_key,
            phone,
            {
                'otp': otp_code,
                'expiry_minutes': str(settings.OTP_EXPIRY_MINUTES),
            },
            idempotency_key=f'otp:{purpose}:{phone}:legacy',
        )

    def send_notification(self, phone, message):
        if settings.DEBUG:
            print(f'[SMS] Notification to {phone}: {message}')
