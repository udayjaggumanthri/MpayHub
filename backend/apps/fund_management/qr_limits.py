"""24h rolling usage limits for PayIn QR collection accounts."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.fund_management.models import LoadMoney, PayInQrAccount
from apps.fund_management.money_utils import money_q

QR_LIMIT_STATUSES = ('PENDING_REVIEW', 'SUCCESS')


def qr_usage_amount_24h(qr_account_id: int, *, exclude_load_money_id: int | None = None) -> Decimal:
    """Sum gross amounts counting toward daily limit (pending review + success)."""
    since = timezone.now() - timedelta(hours=24)
    qs = LoadMoney.objects.filter(
        pay_in_qr_account_id=qr_account_id,
        collection_rail='qr',
        status__in=QR_LIMIT_STATUSES,
        created_at__gte=since,
        is_deleted=False,
    )
    if exclude_load_money_id:
        qs = qs.exclude(pk=exclude_load_money_id)
    agg = qs.aggregate(total=Sum('submitted_amount'))
    raw = agg.get('total')
    if raw is None:
        return money_q(Decimal('0'))
    return money_q(raw)


def qr_usage_map_24h(qr_account_ids: list[int]) -> dict[int, Decimal]:
    if not qr_account_ids:
        return {}
    since = timezone.now() - timedelta(hours=24)
    from django.db.models import F

    rows = (
        LoadMoney.objects.filter(
            pay_in_qr_account_id__in=qr_account_ids,
            collection_rail='qr',
            status__in=QR_LIMIT_STATUSES,
            created_at__gte=since,
            is_deleted=False,
        )
        .values('pay_in_qr_account_id')
        .annotate(total=Sum('submitted_amount'))
    )
    out = {int(qid): money_q(Decimal('0')) for qid in qr_account_ids}
    for row in rows:
        qid = row.get('pay_in_qr_account_id')
        if qid is not None:
            out[int(qid)] = money_q(row.get('total') or Decimal('0'))
    return out


def qr_limit_context(qr: PayInQrAccount, *, used: Decimal | None = None) -> dict:
    used = used if used is not None else qr_usage_amount_24h(qr.pk)
    limit = money_q(qr.daily_limit_24h or Decimal('0'))
    remaining = money_q(max(Decimal('0'), limit - used))
    return {
        'daily_limit': str(limit),
        'daily_used': str(used),
        'remaining_daily_limit': str(remaining),
        'limit_exhausted': remaining <= 0,
    }


def assert_qr_can_accept(qr: PayInQrAccount, amount: Decimal) -> None:
    amt = money_q(amount)
    if qr.max_per_txn is not None and amt > money_q(qr.max_per_txn):
        raise ValueError(f'Amount exceeds per-transaction limit of ₹{qr.max_per_txn} for this QR.')
    ctx = qr_limit_context(qr)
    remaining = Decimal(ctx['remaining_daily_limit'])
    if amt > remaining:
        raise ValueError(
            f'This QR has only ₹{remaining} remaining in its 24-hour limit. Choose another payment method.'
        )
