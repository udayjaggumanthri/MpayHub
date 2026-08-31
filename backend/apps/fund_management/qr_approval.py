"""Admin approve/reject for manual QR pay-in."""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.authentication.models import User
from apps.fund_management.models import LoadMoney, PayInQrApprovalAudit
from apps.fund_management.money_utils import money_q
from apps.fund_management.payin_distribution import _compute_payin_distribution
from apps.fund_management.payin_settlement import finalize_payin_success

logger = logging.getLogger(__name__)

REJECT_REASON_CODES = [
    ('duplicate_utr', 'Duplicate UTR'),
    ('amount_mismatch', 'Amount mismatch'),
    ('invalid_screenshot', 'Invalid or unclear screenshot'),
    ('payment_not_found', 'Payment not found in bank'),
    ('other', 'Other'),
]


@db_transaction.atomic
def approve_qr_payin(
    *,
    load_money: LoadMoney,
    actor: User,
    approved_amount: Decimal,
    internal_note: str = '',
) -> LoadMoney:
    # PostgreSQL does not allow FOR UPDATE on nullable-side OUTER JOINs.
    # Lock LoadMoney only; related rows are read after the lock.
    lm = LoadMoney.objects.select_for_update().get(pk=load_money.pk)
    if lm.collection_rail != 'qr':
        raise ValidationError({'message': 'Not a QR pay-in transaction.'})
    if lm.status == 'SUCCESS':
        return lm
    if lm.status != 'PENDING_REVIEW':
        raise ValidationError({'message': f'Cannot approve transaction in status {lm.status}.'})

    gross = money_q(approved_amount)
    if gross <= 0:
        raise ValidationError({'approved_amount': 'Approved amount must be positive.'})

    package = lm.package
    if not package:
        raise ValidationError({'message': 'Package missing on transaction.'})

    from apps.fund_management.rail_fees import resolve_rail_gateway_fee_pct

    rail_fee = resolve_rail_gateway_fee_pct(
        package, gateway_id=lm.payment_gateway_id, qr_account_id=lm.pay_in_qr_account_id
    )
    dist = _compute_payin_distribution(package, gross, lm.user, gateway_fee_pct=rail_fee)
    lm.amount = gross
    lm.charge = dist['total_deduction']
    lm.net_credit = dist['net_credit']
    lm.fee_breakdown_snapshot = dist['snapshot']
    lm.gateway_transaction_id = lm.utr or lm.transaction_id
    lm.reviewed_by = actor
    lm.reviewed_at = timezone.now()
    lm.save(
        update_fields=[
            'amount',
            'charge',
            'net_credit',
            'fee_breakdown_snapshot',
            'gateway_transaction_id',
            'reviewed_by',
            'reviewed_at',
            'updated_at',
        ]
    )

    meta = dict(lm.payment_meta) if isinstance(lm.payment_meta, dict) else {}
    meta.update(
        {
            'qr_approval': True,
            'submitted_amount': str(lm.submitted_amount or ''),
            'approved_amount': str(gross),
            'qr_account_id': lm.pay_in_qr_account_id,
        }
    )
    lm.payment_meta = meta
    lm.save(update_fields=['payment_meta', 'updated_at'])

    PayInQrApprovalAudit.objects.create(
        load_money=lm,
        action='approved',
        actor=actor,
        submitted_amount=lm.submitted_amount,
        approved_amount=gross,
        internal_note=(internal_note or '')[:2000],
    )

    finalize_payin_success(
        lm,
        gateway_reference=lm.utr or lm.transaction_id,
        payment_method='upi',
        payment_meta=meta,
    )
    lm.refresh_from_db()
    return lm


@db_transaction.atomic
def reject_qr_payin(
    *,
    load_money: LoadMoney,
    actor: User,
    reason_code: str,
    reason_text: str,
    internal_note: str = '',
) -> LoadMoney:
    lm = LoadMoney.objects.select_for_update().get(pk=load_money.pk)
    if lm.collection_rail != 'qr':
        raise ValidationError({'message': 'Not a QR pay-in transaction.'})
    if lm.status == 'SUCCESS':
        raise ValidationError({'message': 'Cannot reject an already successful transaction.'})
    if lm.status != 'PENDING_REVIEW':
        raise ValidationError({'message': f'Cannot reject transaction in status {lm.status}.'})

    label = dict(REJECT_REASON_CODES).get(reason_code, reason_code)
    full_reason = label
    extra = (reason_text or '').strip()
    if extra and extra.lower() != label.lower():
        full_reason = f'{label}: {extra}'

    lm.status = 'FAILED'
    lm.failure_reason = full_reason[:2000]
    lm.reviewed_by = actor
    lm.reviewed_at = timezone.now()
    lm.save(update_fields=['status', 'failure_reason', 'reviewed_by', 'reviewed_at', 'updated_at'])

    PayInQrApprovalAudit.objects.create(
        load_money=lm,
        action='rejected',
        actor=actor,
        submitted_amount=lm.submitted_amount,
        approved_amount=None,
        reject_reason=full_reason[:2000],
        internal_note=(internal_note or '')[:2000],
    )
    return lm


@db_transaction.atomic
def release_qr_utr(
    *,
    load_money: LoadMoney,
    actor: User,
    internal_note: str,
) -> LoadMoney:
    """Clear UTR on a failed QR row so the reference can be reused (admin ops)."""
    note = (internal_note or '').strip()
    if len(note) < 10:
        raise ValidationError({'internal_note': 'Please provide a reason (at least 10 characters).'})

    lm = LoadMoney.objects.select_for_update().get(pk=load_money.pk)
    if lm.collection_rail != 'qr':
        raise ValidationError({'message': 'Not a QR pay-in transaction.'})
    if lm.status != 'FAILED':
        raise ValidationError({'message': 'UTR can only be released on rejected (failed) transactions.'})
    old_utr = (lm.utr or '').strip()
    if not old_utr:
        raise ValidationError({'message': 'This transaction has no UTR to release.'})

    meta = dict(lm.payment_meta) if isinstance(lm.payment_meta, dict) else {}
    meta['released_utr'] = {
        'utr': old_utr,
        'released_by': actor.pk,
        'released_at': timezone.now().isoformat(),
    }
    lm.utr = ''
    lm.payment_meta = meta
    lm.save(update_fields=['utr', 'payment_meta', 'updated_at'])

    PayInQrApprovalAudit.objects.create(
        load_money=lm,
        action='utr_released',
        actor=actor,
        submitted_amount=lm.submitted_amount,
        approved_amount=None,
        reject_reason=old_utr[:2000],
        internal_note=note[:2000],
    )
    return lm
