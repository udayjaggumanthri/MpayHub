from apps.notifications.models import SmsDeliveryLog


def delivery_already_logged(idempotency_key: str) -> bool:
    if not idempotency_key:
        return False
    return SmsDeliveryLog.objects.filter(
        idempotency_key=idempotency_key,
        is_deleted=False,
    ).exists()
