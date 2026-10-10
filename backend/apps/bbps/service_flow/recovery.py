"""Admin recovery for in-flight BBPS payments. Wallet changes go through the shared helpers once."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from apps.bbps.models import BbpsPaymentAttempt
from apps.bbps.service_flow.provider_float import debit_float_for_payment
from apps.bbps.service_flow.status_service import _float_amount_for_attempt
from apps.fund_management.money_utils import money_q


def _append_admin_action(attempt: BbpsPaymentAttempt, *, actor, action: str, note: str) -> None:
    payload = dict(attempt.response_payload or {}) if isinstance(attempt.response_payload, dict) else {}
    marks = list(payload.get('admin_actions') or [])
    marks.append(
        {
            'action': action,
            'note': str(note or '')[:2000],
            'actor_id': getattr(actor, 'pk', None),
            'actor_code': str(getattr(actor, 'user_id', '') or ''),
            'at': timezone.now().isoformat(),
        }
    )
    payload['admin_actions'] = marks[-30:]
    attempt.response_payload = payload


@db_transaction.atomic
def admin_mark_bbps_success(*, attempt: BbpsPaymentAttempt, actor, internal_note: str = '') -> BbpsPaymentAttempt:
    attempt = (
        BbpsPaymentAttempt.objects.select_for_update(of=('self',))
        .select_related('bill_payment', 'user')
        .get(pk=attempt.pk)
    )
    prior = str(attempt.status or '').upper()
    bill = attempt.bill_payment
    already = prior == 'SUCCESS' and bill is not None and str(bill.status or '').upper() == 'SUCCESS'
    _append_admin_action(attempt, actor=actor, action='mark_success', note=internal_note)
    if already and money_q(attempt.wallet_settled_amount or 0) > 0:
        attempt.save(update_fields=['response_payload', 'updated_at'])
        return attempt

    from apps.bbps.service_flow.user_wallet_settlement import settle_payment_hold

    if prior != 'SUCCESS':
        settle_payment_hold(attempt=attempt)
        attempt.status = 'SUCCESS'
        attempt.settled_at = timezone.now()
        attempt.last_error_message = ''
        if bill is not None:
            bill.status = 'SUCCESS'
            bill.failure_reason = ''
            bill.save(update_fields=['status', 'failure_reason'])
        attempt.save(
            update_fields=['status', 'settled_at', 'last_error_message', 'response_payload', 'updated_at']
        )
        debit_float_for_payment(
            attempt.service_id or (bill.service_id if bill else ''),
            _float_amount_for_attempt(attempt),
            payment_attempt=attempt,
            remarks=f'Admin mark SUCCESS {attempt.service_id}',
        )
    else:
        attempt.save(update_fields=['response_payload', 'updated_at'])
    return attempt


@db_transaction.atomic
def admin_mark_bbps_failed(*, attempt: BbpsPaymentAttempt, actor, reason: str = '', internal_note: str = '') -> BbpsPaymentAttempt:
    attempt = (
        BbpsPaymentAttempt.objects.select_for_update(of=('self',))
        .select_related('bill_payment', 'user')
        .get(pk=attempt.pk)
    )
    prior = str(attempt.status or '').upper()
    bill = attempt.bill_payment
    note = str(internal_note or reason or '').strip()
    _append_admin_action(attempt, actor=actor, action='mark_failed', note=note)
    hold = money_q(attempt.wallet_hold_amount or 0)
    settled = money_q(attempt.wallet_settled_amount or 0)
    already = prior == 'FAILED' and hold <= 0 and settled <= 0
    if already:
        attempt.save(update_fields=['response_payload', 'updated_at'])
        return attempt

    from apps.bbps.service_flow.user_wallet_settlement import refund_settled_payment, release_payment_hold

    if settled > 0 and prior != 'FAILED':
        refund_settled_payment(attempt=attempt, reason='admin_mark_failed')
    elif hold > 0:
        release_payment_hold(attempt=attempt, reason=reason or 'admin_mark_failed')

    attempt.status = 'FAILED'
    attempt.settled_at = timezone.now()
    attempt.last_error_message = (reason or 'Marked failed by admin')[:4000]
    attempt.save(
        update_fields=['status', 'settled_at', 'last_error_message', 'response_payload', 'updated_at']
    )
    if bill is not None and str(bill.status or '').upper() != 'FAILED':
        bill.status = 'FAILED'
        bill.failure_reason = attempt.last_error_message
        bill.save(update_fields=['status', 'failure_reason'])
    return attempt


def serialize_bbps_recovery_row(attempt: BbpsPaymentAttempt) -> dict:
    bill = attempt.bill_payment
    user = attempt.user
    payload = attempt.response_payload if isinstance(attempt.response_payload, dict) else {}
    return {
        'id': attempt.pk,
        'bill_payment_id': bill.pk if bill else None,
        'service_id': attempt.service_id or (bill.service_id if bill else ''),
        'request_id': attempt.request_id or (bill.request_id if bill else ''),
        'txn_ref_id': attempt.txn_ref_id or '',
        'status': bill.status if bill else attempt.status,
        'attempt_status': attempt.status,
        'amount': str(bill.amount if bill else Decimal('0')),
        'total_deducted': str(bill.total_deducted if bill else Decimal('0')),
        'wallet_hold_amount': str(attempt.wallet_hold_amount or 0),
        'wallet_settled_amount': str(attempt.wallet_settled_amount or 0),
        'biller': (bill.biller if bill else '') or '',
        'biller_id': attempt.biller_id or (bill.biller_id if bill else ''),
        'failure_reason': (bill.failure_reason if bill else '') or attempt.last_error_message or '',
        'retailer_id': user.pk if user else None,
        'retailer_code': str(getattr(user, 'user_id', '') or ''),
        'retailer_phone': str(getattr(user, 'phone', '') or ''),
        'created_at': attempt.created_at.isoformat() if attempt.created_at else None,
        'last_status_checked_at': (
            attempt.last_status_checked_at.isoformat() if attempt.last_status_checked_at else None
        ),
        'admin_actions': payload.get('admin_actions') or [],
    }


def recovery_queryset():
    return (
        BbpsPaymentAttempt.objects.filter(is_deleted=False)
        .filter(status__in=('PAY_INITIATED', 'AWAITED', 'SUCCESS', 'FAILED'))
        .select_related('bill_payment', 'user')
        .order_by('-created_at')
    )


def stuck_recovery_queryset():
    from django.db.models import Q

    return recovery_queryset().filter(
        Q(status__in=('PAY_INITIATED', 'AWAITED')) | Q(bill_payment__status='PENDING')
    )
