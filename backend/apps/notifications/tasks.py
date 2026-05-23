"""Future Celery hooks — v1 uses synchronous dispatch."""

from apps.notifications.services.dispatch import SmsNotificationService


def send_sms_notification(event_key, phone, context, **kwargs):
    return SmsNotificationService.dispatch(event_key, phone, context, **kwargs)


send_sms_notification.delay = send_sms_notification
