from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.bbps.models import BbpsPaymentAttempt, BbpsStatusPollLog
from apps.bbps.service_flow.provider_float import credit_float_for_refund, debit_float_for_payment
from apps.integrations.bbps_client import BBPSClient

logger = logging.getLogger(__name__)

STATUS_POLL_COOLING_MINUTES = 15
IN_FLIGHT_ATTEMPT_STATUSES = ('PAY_INITIATED', 'AWAITED')


STATUS_MAP = {
    'SUCCESS': 'SUCCESS',
    'FAILURE': 'FAILED',
    'FAILED': 'FAILED',
    'REFUND': 'REFUNDED',
    'REFUNDED': 'REFUNDED',
    'REVERSE': 'REVERSED',
    'REVERSED': 'REVERSED',
}


def _extract_txn_status(payload: dict) -> str:
    if not payload:
        return ''
    if payload.get('txnStatus'):
        return str(payload.get('txnStatus'))
    if isinstance(payload.get('txnList'), list) and payload['txnList']:
        return str(payload['txnList'][0].get('txnStatus') or '')
    node = payload.get('transactionStatusResp') or {}
    if isinstance(node.get('txnList'), list) and node['txnList']:
        return str(node['txnList'][0].get('txnStatus') or '')
    return ''


def _float_amount_for_attempt(attempt: BbpsPaymentAttempt):
    """Bill principal for float tracking (paise → rupees, or BillPayment.amount)."""
    from decimal import Decimal

    if attempt.bill_payment_id and attempt.bill_payment is not None:
        return attempt.bill_payment.amount
    return (Decimal(str(attempt.amount_paise or 0)) / Decimal('100')).quantize(Decimal('0.0001'))


@dataclass
class StatusSyncResult:
    attempt: BbpsPaymentAttempt
    status_changed: bool
    cooling_active: bool
    retry_after_seconds: int
    message: str


def _cooling_remaining_seconds(attempt: BbpsPaymentAttempt, minimum_minutes: int) -> int:
    status = str(attempt.status or '').upper()
    if status not in IN_FLIGHT_ATTEMPT_STATUSES:
        return 0
    anchor = attempt.last_status_checked_at
    if not anchor:
        return 0
    next_allowed = anchor + timedelta(minutes=minimum_minutes)
    now = timezone.now()
    if now >= next_allowed:
        return 0
    return max(1, int((next_allowed - now).total_seconds()))


def due_pending_attempts(*, minimum_minutes: int = STATUS_POLL_COOLING_MINUTES, limit: int = 50):
    cutoff = timezone.now() - timedelta(minutes=max(1, minimum_minutes))
    return (
        BbpsPaymentAttempt.objects.filter(
            is_deleted=False,
            status__in=IN_FLIGHT_ATTEMPT_STATUSES,
        )
        .filter(Q(bill_payment__isnull=True) | Q(bill_payment__status='PENDING'))
        .filter(Q(last_status_checked_at__isnull=True) | Q(last_status_checked_at__lt=cutoff))
        .select_related('bill_payment', 'user')
        .order_by('created_at')[: max(1, limit)]
    )


def sync_due_pending_statuses(*, limit: int = 50, minimum_minutes: int = STATUS_POLL_COOLING_MINUTES) -> int:
    checked = 0
    for attempt in due_pending_attempts(minimum_minutes=minimum_minutes, limit=limit):
        poll_attempt_status(attempt, source='job')
        checked += 1
    return checked


def poll_attempt_status(
    attempt: BbpsPaymentAttempt,
    *,
    requested_by=None,
    source: str = 'job',
    minimum_minutes: int = STATUS_POLL_COOLING_MINUTES,
) -> StatusSyncResult:
    """
    One status-sync used by the scheduled job, the retailer button, and admin recovery.
    Calls transaction-status only. Does not call bill_pay.
    """
    source = str(source or 'job').strip().lower()[:20] or 'job'
    wait = _cooling_remaining_seconds(attempt, minimum_minutes)
    if wait > 0:
        return StatusSyncResult(
            attempt=attempt,
            status_changed=False,
            cooling_active=True,
            retry_after_seconds=wait,
            message=f'Status check is cooling. Retry after {wait} seconds.',
        )

    prior_status = str(attempt.status or '').upper()
    if attempt.txn_ref_id:
        track_type = 'TRANS_REF_ID'
        track_value = attempt.txn_ref_id
    elif attempt.request_id:
        track_type = 'REQUEST_ID'
        track_value = attempt.request_id
    else:
        track_type = 'REQUEST_ID'
        track_value = attempt.service_id or ''

    payload: dict = {}
    error_message = ''
    if not track_value:
        error_message = 'No BillAvenue reference to check yet.'
    else:
        try:
            client = BBPSClient()
            raw = client.transaction_status(track_type=track_type, track_value=track_value)
            payload = raw if isinstance(raw, dict) else {}
        except Exception as exc:
            logger.exception('BBPS transaction-status failed for %s', attempt.service_id)
            error_message = str(exc)
            payload = {'error': error_message}

    txn_status = _extract_txn_status(payload).upper()
    mapped = STATUS_MAP.get(txn_status)
    status_changed = bool(mapped and mapped != prior_status)

    now = timezone.now()
    attempt.last_status_checked_at = now
    if mapped:
        attempt.status = mapped
        if mapped in ('SUCCESS', 'FAILED', 'REFUNDED', 'REVERSED'):
            attempt.settled_at = now
    update_fields = ['last_status_checked_at', 'updated_at']
    if mapped:
        update_fields.extend(['status', 'settled_at'])
    attempt.save(update_fields=update_fields)

    if attempt.bill_payment_id and mapped:
        bill = attempt.bill_payment
        if mapped == 'SUCCESS':
            bill.status = 'SUCCESS'
            bill.failure_reason = ''
            bill.save(update_fields=['status', 'failure_reason'])
        elif mapped in ('FAILED', 'REFUNDED', 'REVERSED'):
            bill.status = 'FAILED'
            if mapped in ('REFUNDED', 'REVERSED'):
                bill.failure_reason = f'Status changed to {mapped}'
            elif not bill.failure_reason:
                bill.failure_reason = 'BillAvenue reported failure'
            bill.save(update_fields=['status', 'failure_reason'])

    from apps.bbps.service_flow.user_wallet_settlement import (
        refund_settled_payment,
        release_payment_hold,
        settle_payment_hold,
    )

    if mapped == 'SUCCESS' and prior_status != 'SUCCESS':
        try:
            settle_payment_hold(attempt=attempt)
        except Exception:
            logger.exception('BBPS user wallet settle failed on poll for %s', attempt.service_id)
    elif mapped == 'FAILED' and prior_status not in ('FAILED', 'SUCCESS', 'REFUNDED', 'REVERSED'):
        release_payment_hold(attempt=attempt, reason='status_poll_failed')
    elif mapped in ('REFUNDED', 'REVERSED') and prior_status not in ('REFUNDED', 'REVERSED'):
        refund_settled_payment(attempt=attempt, reason=mapped.lower())

    sid = attempt.service_id or (attempt.bill_payment.service_id if attempt.bill_payment_id else '')
    amt = _float_amount_for_attempt(attempt)
    if mapped == 'SUCCESS' and prior_status != 'SUCCESS':
        debit_float_for_payment(sid, amt, payment_attempt=attempt, remarks=f'Status poll SUCCESS {sid}')
    elif mapped in ('REFUNDED', 'REVERSED') and prior_status not in ('REFUNDED', 'REVERSED'):
        credit_float_for_refund(sid, amt, payment_attempt=attempt, remarks=f'Status poll {mapped} {sid}')

    BbpsStatusPollLog.objects.create(
        attempt=attempt,
        track_type=track_type,
        track_value=track_value,
        response_code=str(payload.get('responseCode') or ''),
        txn_status=txn_status or ('NO_CHANGE' if not mapped else txn_status),
        response_payload=payload,
        error_message=error_message,
        requested_by=requested_by if getattr(requested_by, 'pk', None) else None,
        source=source,
        status_changed=status_changed,
    )

    if status_changed:
        from apps.bbps.notifications import notify_payment_attempt_status

        notify_payment_attempt_status(attempt, source='status_poll')
        message = f'Status updated to {attempt.status}.'
    elif mapped:
        message = 'Status unchanged.'
    elif prior_status in ('SUCCESS', 'FAILED', 'REFUNDED', 'REVERSED'):
        message = f'Saved status stays {prior_status}. BillAvenue did not return a new final status.'
    else:
        message = 'BillAvenue has not confirmed a final result. Payment stays pending.'

    return StatusSyncResult(
        attempt=attempt,
        status_changed=status_changed,
        cooling_active=False,
        retry_after_seconds=minimum_minutes * 60,
        message=message,
    )
