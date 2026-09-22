from apps.notifications.models import EmailDeliveryLog


def email_delivery_already_logged(idempotency_key: str) -> bool:
    """True when this idempotency key already has any delivery log row."""
    if not idempotency_key:
        return False
    return EmailDeliveryLog.objects.filter(
        idempotency_key=idempotency_key,
        is_deleted=False,
    ).exists()
