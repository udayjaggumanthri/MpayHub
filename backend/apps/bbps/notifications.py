"""
BBPS payment status SMS — shared idempotency across sync, poll, and webhook paths.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from apps.bbps.payment_notification_context import build_payment_notification_context

if TYPE_CHECKING:
    from apps.bbps.models import BbpsPaymentAttempt

STATUS_TO_EVENT = {
    'SUCCESS': 'bbps.payment.success',
    'FAILED': 'bbps.payment.failed',
    'AWAITED': 'bbps.payment.awaited',
}


def notify_payment_attempt_status(attempt: 'BbpsPaymentAttempt', *, source: str = '') -> None:
    """
    Dispatch SMS and email for terminal or awaited BBPS attempt status. Never raises.
    """
    status = (attempt.status or '').upper()
    event_key = STATUS_TO_EVENT.get(status)
    if not event_key:
        return

    context = build_payment_notification_context(attempt, status)
    idem = f'bbps:{attempt.pk}:{status}'

    try:
        from apps.notifications.services.dispatch import SmsNotificationService

        phone = getattr(attempt.user, 'phone', '') or ''
        SmsNotificationService.dispatch(
            event_key,
            phone,
            context,
            user_id=attempt.user_id,
            idempotency_key=idem,
        )
    except Exception:
        pass

    try:
        from apps.notifications.services.email_dispatch import EmailNotificationService

        to_email = (getattr(attempt.user, 'email', None) or '').strip()
        if to_email:
            EmailNotificationService.dispatch(
                event_key,
                to_email,
                context,
                user_id=attempt.user_id,
                idempotency_key=f'email:{idem}',
            )
    except Exception:
        pass


def notify_complaint_registered(complaint) -> None:
    """Email after BBPS complaint registered with provider."""
    try:
        from apps.notifications.services.email_dispatch import EmailNotificationService

        user = complaint.user
        to_email = (getattr(user, 'email', None) or '').strip()
        if not to_email:
            return
        EmailNotificationService.dispatch(
            'complaint.registered',
            to_email,
            {
                'complaint_id': str(complaint.complaint_id or ''),
                'txn_ref': str(complaint.txn_ref_id or ''),
                'disposition': str(complaint.complaint_disposition or ''),
                'status': str(complaint.complaint_status or ''),
            },
            user_id=user.pk,
            idempotency_key=f'complaint:{complaint.pk}',
        )
    except Exception:
        pass
