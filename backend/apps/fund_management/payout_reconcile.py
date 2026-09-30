"""
Admin / ops reconcile for payouts stuck in PENDING (missed provider callbacks).

Does not change the happy-path hold → callback flow. Only acts on PENDING rows
after an operator confirms bank/provider outcome.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.db import transaction as db_transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.fund_management.models import Payout
from apps.fund_management.money_utils import money_q
from apps.fund_management.payout_orchestrator import _log_event, _notify_failed, _settle_success
from apps.wallets.models import Wallet

logger = logging.getLogger(__name__)

DEFAULT_STUCK_MINUTES = 30


def pending_payout_queryset(*, min_age_minutes: int | None = None):
    qs = (
        Payout.objects.filter(status='PENDING', is_deleted=False)
        .select_related('user', 'bank_account')
        .order_by('created_at')
    )
    if min_age_minutes is not None and min_age_minutes > 0:
        cutoff = timezone.now() - timedelta(minutes=min_age_minutes)
        qs = qs.filter(created_at__lte=cutoff)
    return qs


def payout_recovery_stats(*, stuck_minutes: int = DEFAULT_STUCK_MINUTES) -> dict[str, Any]:
    stuck_minutes = max(1, int(stuck_minutes or DEFAULT_STUCK_MINUTES))
    cutoff = timezone.now() - timedelta(minutes=stuck_minutes)
    base = Payout.objects.filter(status='PENDING', is_deleted=False)
    agg = base.aggregate(
        pending_count=Count('id'),
        held_amount=Sum('total_deducted'),
        stuck_count=Count('id', filter=Q(created_at__lte=cutoff)),
    )
    return {
        'pending_count': int(agg.get('pending_count') or 0),
        'stuck_count': int(agg.get('stuck_count') or 0),
        'held_amount': str(money_q(agg.get('held_amount') or 0)),
        'stuck_after_minutes': stuck_minutes,
    }


def serialize_payout_recovery_row(payout: Payout) -> dict[str, Any]:
    age_seconds = 0
    if payout.created_at:
        age_seconds = max(0, int((timezone.now() - payout.created_at).total_seconds()))
    bank = payout.bank_account
    user = payout.user
    acct = str(getattr(bank, 'account_number', '') or '')
    masked = f'XXXX{acct[-4:]}' if len(acct) >= 4 else (acct or '—')
    return {
        'id': payout.id,
        'transaction_id': payout.transaction_id,
        'merchant_ref_id': payout.merchant_ref_id or payout.transaction_id,
        'status': payout.status,
        'amount': str(money_q(payout.amount)),
        'charge': str(money_q(payout.charge)),
        'total_deducted': str(money_q(payout.total_deducted)),
        'transfer_mode': payout.transfer_mode,
        'provider_code': payout.provider_code or '',
        'provider_txn_id': payout.provider_txn_id or '',
        'provider_status_code': payout.provider_status_code or '',
        'rrn': payout.rrn or '',
        'callback_received_at': (
            payout.callback_received_at.isoformat() if payout.callback_received_at else None
        ),
        'created_at': payout.created_at.isoformat() if payout.created_at else None,
        'age_seconds': age_seconds,
        'age_label': _format_age(age_seconds),
        'is_stuck': age_seconds >= DEFAULT_STUCK_MINUTES * 60,
        'user': {
            'id': user.pk if user else None,
            'user_id': getattr(user, 'user_id', '') or '',
            'name': (
                f'{getattr(user, "first_name", "") or ""} {getattr(user, "last_name", "") or ""}'
            ).strip()
            or getattr(user, 'email', '')
            or '',
            'phone': getattr(user, 'phone', '') or '',
            'role': getattr(user, 'role', '') or '',
        },
        'bank_account': {
            'bank_name': getattr(bank, 'bank_name', '') or '',
            'account_masked': masked,
            'ifsc': getattr(bank, 'ifsc', '') or '',
            'account_holder_name': (
                getattr(bank, 'beneficiary_name', None)
                or getattr(bank, 'account_holder_name', '')
                or ''
            ),
        },
    }


def _format_age(seconds: int) -> str:
    if seconds < 60:
        return f'{seconds}s'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes}m'
    hours = minutes // 60
    rem_m = minutes % 60
    if hours < 48:
        return f'{hours}h {rem_m}m' if rem_m else f'{hours}h'
    days = hours // 24
    return f'{days}d'


def _append_reconcile_meta(payout: Payout, payload: dict) -> None:
    meta = payout.response_meta if isinstance(payout.response_meta, dict) else {}
    history = meta.get('admin_reconcile')
    if not isinstance(history, list):
        history = []
    history.append(payload)
    meta['admin_reconcile'] = history[-20:]
    payout.response_meta = meta


def admin_mark_payout_success(
    *,
    payout: Payout,
    actor,
    rrn: str = '',
    provider_txn_id: str = '',
    internal_note: str = '',
) -> Payout:
    """
    Confirm bank paid: settle hold → SUCCESS.
    Requires operator confirmation; does not call the provider.
    """
    note = (internal_note or '').strip()
    if len(note) < 5:
        raise ValidationError({'internal_note': 'Add a short note (why this is confirmed SUCCESS).'})
    rrn_s = (rrn or '').strip()
    provider_txn = (provider_txn_id or '').strip()

    with db_transaction.atomic():
        locked = Payout.objects.select_for_update().select_related('user', 'bank_account').get(pk=payout.pk)
        if locked.status == 'SUCCESS':
            return locked
        if locked.status != 'PENDING':
            raise ValidationError({'status': f'Only PENDING payouts can be marked SUCCESS (now {locked.status}).'})

        _append_reconcile_meta(
            locked,
            {
                'action': 'success',
                'actor_id': getattr(actor, 'pk', None),
                'actor_user_id': getattr(actor, 'user_id', '') or '',
                'note': note[:500],
                'rrn': rrn_s,
                'provider_txn_id': provider_txn,
                'at': timezone.now().isoformat(),
            },
        )
        locked.save(update_fields=['response_meta', 'updated_at'])

        _settle_success(
            locked,
            rrn=rrn_s or locked.rrn or '',
            provider_txn_id=provider_txn or locked.provider_txn_id or '',
            status_code=locked.provider_status_code or '000',
            response_message=f'Admin reconcile SUCCESS: {note[:200]}',
            provider_charges=None,
        )

    locked.refresh_from_db()
    _log_event(
        payout=locked,
        provider_code=locked.provider_code or 'manual',
        direction='inbound',
        event_type='admin_reconcile_success',
        merchant_ref_id=locked.transaction_id,
        payload={
            'actor_id': getattr(actor, 'pk', None),
            'note': note[:500],
            'rrn': rrn_s,
            'provider_txn_id': provider_txn,
        },
        notes=note[:500],
    )
    return locked


def admin_mark_payout_failed(
    *,
    payout: Payout,
    actor,
    reason: str = '',
    internal_note: str = '',
) -> Payout:
    """
    Confirm bank did not pay: release hold → FAILED.
    """
    note = (internal_note or '').strip()
    if len(note) < 5:
        raise ValidationError({'internal_note': 'Add a short note (why this is confirmed FAILED).'})
    reason_s = (reason or '').strip() or 'Admin reconcile: provider/bank confirmed failure'

    with db_transaction.atomic():
        locked = Payout.objects.select_for_update().select_related('user').get(pk=payout.pk)
        if locked.status == 'FAILED':
            return locked
        if locked.status != 'PENDING':
            raise ValidationError({'status': f'Only PENDING payouts can be marked FAILED (now {locked.status}).'})

        wallet = Wallet.get_wallet(locked.user, 'main')
        try:
            wallet.release(
                locked.total_deducted,
                reference=locked.transaction_id,
                description=f'Payout release {locked.transaction_id} (admin)',
            )
        except Exception:
            logger.exception('Admin reconcile release failed for %s', locked.transaction_id)
            raise ValidationError({'wallet': 'Could not release held balance. Contact engineering.'})

        _append_reconcile_meta(
            locked,
            {
                'action': 'failed',
                'actor_id': getattr(actor, 'pk', None),
                'actor_user_id': getattr(actor, 'user_id', '') or '',
                'note': note[:500],
                'reason': reason_s[:500],
                'at': timezone.now().isoformat(),
            },
        )
        locked.status = 'FAILED'
        locked.failure_reason = reason_s[:2000]
        locked.save(update_fields=['status', 'failure_reason', 'response_meta', 'updated_at'])

    locked.refresh_from_db()
    _log_event(
        payout=locked,
        provider_code=locked.provider_code or 'manual',
        direction='inbound',
        event_type='admin_reconcile_failed',
        merchant_ref_id=locked.transaction_id,
        payload={
            'actor_id': getattr(actor, 'pk', None),
            'note': note[:500],
            'reason': reason_s[:500],
        },
        notes=note[:500],
    )
    _notify_failed(locked.user, locked, reason_s)
    return locked
