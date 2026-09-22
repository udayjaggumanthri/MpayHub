"""
Channel (and operator) dashboard home widgets: recent activity + period summary.

Recent rows merge operational tables (Load Money, Payout, BBPS, AEPS, CMS).
Credits / debits come from the signed-in user's main-wallet passbook so they
match the ledger the user already sees. Operators see platform-wide numbers.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet, Sum
from django.utils import timezone

from apps.bbps.models import BillPayment
from apps.core.roles import is_platform_operator
from apps.fund_management.models import LoadMoney, Payout
from apps.transactions.models import PassbookEntry

VALID_INTERVALS = frozenset({'daily', 'weekly', 'monthly'})
RECENT_LIMIT_DEFAULT = 8
RECENT_LIMIT_MAX = 15
PER_SOURCE_FETCH = 15


def _local_today() -> date:
    return timezone.localdate()


def _normalize_status(raw: str | None) -> str:
    st = (raw or 'PENDING').strip().upper()
    if st in {'SUCCESS', 'RECONCILED'}:
        return 'SUCCESS'
    if st in {'FAILED', 'FAILURE', 'TIMEOUT', 'EXPIRED'}:
        return 'FAILED'
    if st in {'PENDING', 'INITIATED'}:
        return 'PENDING'
    return 'PENDING'


def _scope_user_kwargs(user) -> dict[str, Any]:
    if is_platform_operator(user):
        return {}
    return {'user': user}


def _deleted_ok(qs: QuerySet) -> QuerySet:
    if any(f.name == 'is_deleted' for f in qs.model._meta.fields):
        return qs.filter(is_deleted=False)
    return qs


def _period_for_interval(interval: str) -> tuple[date, date, date, date]:
    """Return (current_from, current_to, previous_from, previous_to)."""
    interval = (interval or 'daily').strip().lower()
    if interval not in VALID_INTERVALS:
        interval = 'daily'
    today = _local_today()
    if interval == 'weekly':
        current_from = today - timedelta(days=6)
        current_to = today
        prev_to = current_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=6)
    elif interval == 'monthly':
        current_from = today.replace(day=1)
        current_to = today
        span = (current_to - current_from).days + 1
        prev_to = current_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=span - 1)
    else:
        current_from = current_to = today
        prev_from = prev_to = today - timedelta(days=1)
    return current_from, current_to, prev_from, prev_to


def _money(value) -> str:
    return f'{Decimal(value or 0):.2f}'


def _pct_change(current: Decimal, previous: Decimal) -> float:
    if previous == 0:
        if current == 0:
            return 0.0
        return 100.0
    return float(((current - previous) / previous) * Decimal('100'))


def _row(
    *,
    module: str,
    type_label: str,
    ref: str,
    amount,
    status: str,
    created_at,
    href: str,
    signed: str,
) -> dict[str, Any]:
    return {
        'id': f'{module}:{ref}',
        'module': module,
        'type': type_label,
        'reference': ref,
        'amount': _money(amount),
        'signed': signed,
        'status': _normalize_status(status),
        'created_at': created_at.isoformat() if created_at else None,
        'href': href,
    }


def _collect_recent(user, limit: int) -> list[dict[str, Any]]:
    scope = _scope_user_kwargs(user)
    rows: list[dict[str, Any]] = []

    for obj in _deleted_ok(LoadMoney.objects.filter(**scope)).order_by('-created_at')[:PER_SOURCE_FETCH]:
        rows.append(
            _row(
                module='payin',
                type_label='Load Money',
                ref=obj.transaction_id,
                amount=obj.amount,
                status=obj.status,
                created_at=obj.created_at,
                href='/reports/payin',
                signed='credit',
            )
        )

    for obj in _deleted_ok(Payout.objects.filter(**scope)).order_by('-created_at')[:PER_SOURCE_FETCH]:
        rows.append(
            _row(
                module='payout',
                type_label='Payout',
                ref=obj.transaction_id,
                amount=obj.amount,
                status=obj.status,
                created_at=obj.created_at,
                href='/reports/payout',
                signed='debit',
            )
        )

    for obj in _deleted_ok(BillPayment.objects.filter(**scope)).order_by('-created_at')[:PER_SOURCE_FETCH]:
        rows.append(
            _row(
                module='bbps',
                type_label='BBPS',
                ref=obj.service_id,
                amount=obj.amount,
                status=obj.status,
                created_at=obj.created_at,
                href='/reports/bbps',
                signed='debit',
            )
        )

    try:
        from apps.aeps.models import AepsTransaction

        for obj in _deleted_ok(AepsTransaction.objects.filter(**scope)).order_by('-created_at')[:PER_SOURCE_FETCH]:
            rows.append(
                _row(
                    module='aeps',
                    type_label='AEPS',
                    ref=obj.merchant_tran_id,
                    amount=obj.amount,
                    status=obj.status,
                    created_at=obj.created_at,
                    href='/aeps/reports',
                    signed='credit',
                )
            )
    except Exception:  # noqa: BLE001
        pass

    try:
        from apps.cms.models import CmsTransaction

        for obj in _deleted_ok(CmsTransaction.objects.filter(**scope)).order_by('-created_at')[:PER_SOURCE_FETCH]:
            rows.append(
                _row(
                    module='cms',
                    type_label='CMS',
                    ref=obj.merchant_transaction_id,
                    amount=obj.amount,
                    status=obj.status,
                    created_at=obj.created_at,
                    href='/cms/reports',
                    signed='credit',
                )
            )
    except Exception:  # noqa: BLE001
        pass

    rows.sort(key=lambda r: r.get('created_at') or '', reverse=True)
    return rows[:limit]


def get_recent_dashboard_transactions(user, limit: int = RECENT_LIMIT_DEFAULT) -> dict[str, Any]:
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = RECENT_LIMIT_DEFAULT
    limit = max(1, min(limit, RECENT_LIMIT_MAX))
    return {
        'items': _collect_recent(user, limit),
        'limit': limit,
        'scope': 'platform' if is_platform_operator(user) else 'self',
    }


def _passbook_totals(user, date_from: date, date_to: date) -> tuple[Decimal, Decimal]:
    qs = _deleted_ok(PassbookEntry.objects.filter(wallet_type='main'))
    if not is_platform_operator(user):
        qs = qs.filter(user=user)
    qs = qs.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
    agg = qs.aggregate(credits=Sum('credit_amount'), debits=Sum('debit_amount'))
    return Decimal(agg.get('credits') or 0), Decimal(agg.get('debits') or 0)


def _txn_count(user, date_from: date, date_to: date) -> int:
    scope = _scope_user_kwargs(user)
    period = {'created_at__date__gte': date_from, 'created_at__date__lte': date_to}
    total = 0
    for model in (LoadMoney, Payout, BillPayment):
        total += _deleted_ok(model.objects.filter(**scope, **period)).count()
    try:
        from apps.aeps.models import AepsTransaction

        total += _deleted_ok(AepsTransaction.objects.filter(**scope, **period)).count()
    except Exception:  # noqa: BLE001
        pass
    try:
        from apps.cms.models import CmsTransaction

        total += _deleted_ok(CmsTransaction.objects.filter(**scope, **period)).count()
    except Exception:  # noqa: BLE001
        pass
    return total


def get_todays_summary(user, interval: str = 'daily') -> dict[str, Any]:
    interval = (interval or 'daily').strip().lower()
    if interval not in VALID_INTERVALS:
        interval = 'daily'
    current_from, current_to, prev_from, prev_to = _period_for_interval(interval)

    credits, debits = _passbook_totals(user, current_from, current_to)
    prev_credits, prev_debits = _passbook_totals(user, prev_from, prev_to)
    count = _txn_count(user, current_from, current_to)
    prev_count = _txn_count(user, prev_from, prev_to)

    return {
        'interval': interval,
        'period': {
            'from': current_from.isoformat(),
            'to': current_to.isoformat(),
        },
        'previous_period': {
            'from': prev_from.isoformat(),
            'to': prev_to.isoformat(),
        },
        'scope': 'platform' if is_platform_operator(user) else 'self',
        'total_credits': _money(credits),
        'total_debits': _money(debits),
        'transaction_count': count,
        'credits_change_pct': round(_pct_change(credits, prev_credits), 1),
        'debits_change_pct': round(_pct_change(debits, prev_debits), 1),
        'count_change_pct': round(_pct_change(Decimal(count), Decimal(prev_count)), 1),
    }
