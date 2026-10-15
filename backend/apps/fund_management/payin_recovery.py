"""Admin pay-in recovery. Does not change payout or BBPS rows."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction as db_transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.exceptions import InsufficientBalance
from apps.fund_management.models import LoadMoney
from apps.fund_management.money_utils import money_q
from apps.fund_management.payin_distribution import _compute_payin_distribution
from apps.fund_management.payin_settlement import (
    _locked_fee_snapshot,
    _passbook_credit,
    _passbook_debit,
    finalize_payin_success,
)
from apps.fund_management.qr_approval import approve_qr_payin, reject_qr_payin
from apps.transactions.models import Transaction


def _money_or_none(value):
    if value in (None, ''):
        return None
    try:
        return money_q(value)
    except Exception:
        return None


def _package_rate_net(lm: LoadMoney):
    package = lm.package
    if package is None or lm.status != 'SUCCESS':
        return None
    try:
        dist = _compute_payin_distribution(
            package,
            money_q(lm.amount),
            lm.user,
            gateway_fee_pct=package.gateway_fee_pct,
        )
    except Exception:
        return None
    return dist['net_credit']


def _adjustment(lm: LoadMoney) -> dict:
    meta = lm.payment_meta if isinstance(lm.payment_meta, dict) else {}
    raw = meta.get('fee_adjustment')
    return raw if isinstance(raw, dict) else {}


def _user_name(user) -> str:
    if user is None:
        return ''
    try:
        profile = user.profile
    except ObjectDoesNotExist:
        return ''
    return f'{profile.first_name or ""} {profile.last_name or ""}'.strip()


def serialize_payin_recovery_row(lm: LoadMoney) -> dict:
    snap = _locked_fee_snapshot(lm) or {}
    credited = money_q(lm.net_credit)
    locked = _money_or_none(snap.get('net_credit'))
    package_rate = _package_rate_net(lm)
    adjustment = _adjustment(lm)
    user = lm.user
    gateway_name = lm.payment_gateway.name if lm.payment_gateway_id and lm.payment_gateway else ''
    qr_name = lm.pay_in_qr_account.display_name if lm.pay_in_qr_account_id and lm.pay_in_qr_account else ''
    return {
        'id': lm.pk,
        'transaction_id': lm.transaction_id,
        'status': lm.status,
        'collection_rail': lm.collection_rail,
        'gross': str(money_q(lm.amount)),
        'charge': str(money_q(lm.charge)),
        'credited_net': str(credited),
        'locked_net': str(locked) if locked is not None else '',
        'package_rate_net': str(package_rate) if package_rate is not None else '',
        'locked_gap': str(money_q(locked - credited)) if locked is not None else '0',
        'package_rate_gap': str(money_q(package_rate - credited)) if package_rate is not None else '0',
        'adjustment_applied': bool(adjustment.get('applied')),
        'gateway_name': gateway_name or lm.gateway or '',
        'qr_name': qr_name,
        'utr': lm.utr or '',
        'gateway_transaction_id': lm.gateway_transaction_id or '',
        'failure_reason': lm.failure_reason or '',
        'created_at': lm.created_at.isoformat() if lm.created_at else '',
        'user_id': getattr(user, 'user_id', '') or '',
        'user_name': _user_name(user),
        'user_phone': getattr(user, 'phone', '') or '',
        'user_email': getattr(user, 'email', '') or '',
        'package_name': lm.package.display_name if lm.package_id and lm.package else '',
    }


def _needs_attention(lm: LoadMoney) -> bool:
    if lm.status in ('PENDING', 'PENDING_REVIEW'):
        return True
    if lm.status != 'SUCCESS' or _adjustment(lm).get('applied'):
        return False
    row = serialize_payin_recovery_row(lm)
    return money_q(row['locked_gap']) != 0 or money_q(row['package_rate_gap']) != 0


def payin_recovery_queryset(q: str = ''):
    base = (
        LoadMoney.objects.filter(is_deleted=False)
        .select_related('user', 'user__profile', 'package', 'payment_gateway', 'pay_in_qr_account')
        .order_by('-created_at')
    )
    text = (q or '').strip()
    if text:
        return base.filter(
            Q(transaction_id__icontains=text)
            | Q(utr__icontains=text)
            | Q(gateway_transaction_id__icontains=text)
            | Q(user__phone__icontains=text)
            | Q(user__user_id__icontains=text)
            | Q(user__email__icontains=text)
        )
    open_rows = list(base.filter(status__in=['PENDING', 'PENDING_REVIEW'])[:200])
    since = timezone.now() - timedelta(days=14)
    recent_success = base.filter(status='SUCCESS', created_at__gte=since)[:100]
    seen = {row.pk for row in open_rows}
    for lm in recent_success:
        if lm.pk in seen:
            continue
        if _needs_attention(lm):
            open_rows.append(lm)
    return open_rows


def payin_recovery_stats() -> dict:
    pending = LoadMoney.objects.filter(is_deleted=False, status='PENDING').count()
    review = LoadMoney.objects.filter(is_deleted=False, status='PENDING_REVIEW').count()
    return {
        'pending_count': pending,
        'review_count': review,
        'open_count': pending + review,
    }


@db_transaction.atomic
def admin_mark_payin_success(*, load_money: LoadMoney, actor, utr: str = '', internal_note: str = '', approved_amount=None):
    lm = LoadMoney.objects.select_for_update().get(pk=load_money.pk)
    if lm.status == 'SUCCESS':
        return lm
    note = (internal_note or '').strip()
    if lm.collection_rail == 'qr' or lm.status == 'PENDING_REVIEW':
        if lm.status != 'PENDING_REVIEW':
            raise ValidationError({'message': 'This QR pay-in is not waiting for review.'})
        return approve_qr_payin(
            load_money=lm,
            actor=actor,
            approved_amount=money_q(approved_amount if approved_amount not in (None, '') else lm.amount),
            internal_note=note,
        )
    if lm.status != 'PENDING':
        raise ValidationError({'message': f'Cannot complete a pay-in in status {lm.status}.'})
    reference = (utr or lm.utr or lm.gateway_transaction_id or lm.transaction_id).strip()
    meta = {'recovery_note': note[:500]} if note else None
    finalize_payin_success(
        lm,
        gateway_reference=reference,
        payment_method=lm.payment_method or 'gateway',
        payment_meta=meta,
    )
    lm.refresh_from_db()
    return lm


@db_transaction.atomic
def admin_mark_payin_failed(*, load_money: LoadMoney, actor, reason: str = '', internal_note: str = ''):
    lm = LoadMoney.objects.select_for_update().get(pk=load_money.pk)
    if lm.status == 'SUCCESS':
        raise ValidationError({'message': 'This pay-in is already credited. Use the fee adjustment instead.'})
    if lm.status == 'FAILED':
        return lm
    if lm.collection_rail == 'qr' or lm.status == 'PENDING_REVIEW':
        return reject_qr_payin(
            load_money=lm,
            actor=actor,
            reason_code='other',
            reason_text=(reason or 'Marked failed from pay-in recovery')[:500],
            internal_note=internal_note or '',
        )
    if lm.status != 'PENDING':
        raise ValidationError({'message': f'Cannot fail a pay-in in status {lm.status}.'})
    lm.status = 'FAILED'
    lm.failure_reason = (reason or 'Marked failed from pay-in recovery')[:2000]
    lm.reviewed_by = actor
    lm.reviewed_at = timezone.now()
    lm.save(update_fields=['status', 'failure_reason', 'reviewed_by', 'reviewed_at', 'updated_at'])
    return lm


@db_transaction.atomic
def admin_adjust_payin_fee(*, load_money: LoadMoney, actor, target: str):
    """Move one user's main wallet from the credited net to the chosen quote. Once per row."""
    lm = (
        LoadMoney.objects.select_for_update()
        .select_related('user', 'user__profile', 'package', 'payment_gateway', 'pay_in_qr_account')
        .get(pk=load_money.pk)
    )
    if lm.status != 'SUCCESS':
        raise ValidationError({'message': 'Only a credited pay-in can be adjusted.'})
    if _adjustment(lm).get('applied'):
        raise ValidationError({'message': 'This pay-in was already adjusted.'})
    credited = money_q(lm.net_credit)
    if target == 'locked':
        snap = _locked_fee_snapshot(lm)
        if snap is None:
            raise ValidationError({'message': 'This pay-in has no locked quote.'})
        target_net = money_q(snap['net_credit'])
    elif target == 'package_rate':
        target_net = _package_rate_net(lm)
        if target_net is None:
            raise ValidationError({'message': 'Package rate could not be calculated.'})
    else:
        raise ValidationError({'message': 'Choose the locked quote or the package rate.'})
    delta = money_q(target_net - credited)
    if delta == 0:
        raise ValidationError({'message': 'The credited amount already matches that quote.'})
    reference = f'{lm.transaction_id}:fee-adjust'
    description = (
        f'Pay-in fee correction on {lm.transaction_id}: '
        f'₹{credited} to ₹{target_net}'
    )
    try:
        if delta > 0:
            _passbook_credit(
                lm.user,
                'main',
                'LOAD MONEY',
                reference,
                description,
                delta,
                reference,
                initiator_user=actor,
            )
        else:
            _passbook_debit(
                lm.user,
                'main',
                'LOAD MONEY',
                reference,
                description,
                abs(delta),
                reference,
                initiator_user=actor,
            )
    except InsufficientBalance as exc:
        raise ValidationError({'message': str(exc) or 'Wallet balance is too low for this correction.'}) from exc

    gross = money_q(lm.amount)
    lm.net_credit = target_net
    lm.charge = money_q(gross - target_net)
    meta = dict(lm.payment_meta) if isinstance(lm.payment_meta, dict) else {}
    meta['fee_adjustment'] = {
        'applied': True,
        'target': target,
        'from_net': str(credited),
        'to_net': str(target_net),
        'delta': str(delta),
        'actor_id': getattr(actor, 'pk', None),
    }
    lm.payment_meta = meta
    lm.save(update_fields=['net_credit', 'charge', 'payment_meta', 'updated_at'])
    Transaction.objects.filter(service_id=lm.transaction_id, transaction_type='payin').update(
        net_amount=target_net,
        charge=lm.charge,
    )
    return lm
