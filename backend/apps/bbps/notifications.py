"""
BBPS payment status SMS — shared idempotency across sync, poll, and webhook paths.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.bbps.models import BbpsPaymentAttempt

STATUS_TO_EVENT = {
    'SUCCESS': 'bbps.payment.success',
    'FAILED': 'bbps.payment.failed',
    'AWAITED': 'bbps.payment.awaited',
}


def _amount_str(attempt: 'BbpsPaymentAttempt') -> str:
    paise = int(attempt.amount_paise or 0)
    return str((Decimal(paise) / Decimal('100')).quantize(Decimal('0.01')))


def _biller_name(attempt: 'BbpsPaymentAttempt') -> str:
    bill_payment = attempt.bill_payment
    if bill_payment and getattr(bill_payment, 'biller', None):
        return str(bill_payment.biller)
    payload = attempt.request_payload if isinstance(attempt.request_payload, dict) else {}
    return str(payload.get('biller') or payload.get('biller_name') or attempt.biller_id or 'BBPS')


def _payment_context(attempt: 'BbpsPaymentAttempt', status: str) -> dict:
    context = {
        'biller': _biller_name(attempt),
        'amount': _amount_str(attempt),
        'service_id': attempt.service_id or '',
    }
    if status in ('SUCCESS', 'AWAITED'):
        context['txn_ref'] = attempt.txn_ref_id or attempt.approval_ref_number or ''
    if status == 'FAILED':
        context['reason'] = (attempt.last_error_message or '')[:200]
    return context


def notify_payment_attempt_status(attempt: 'BbpsPaymentAttempt', *, source: str = '') -> None:
    """
    Dispatch SMS and email for terminal or awaited BBPS attempt status. Never raises.
    """
    status = (attempt.status or '').upper()
    event_key = STATUS_TO_EVENT.get(status)
    if not event_key:
        return

    context = _payment_context(attempt, status)
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
