"""
Admin dashboard transaction status counts — platform-wide aggregates from operational tables.

Pay-in / payout / BBPS pending counts live on LoadMoney, Payout, and BillPayment respectively
(not only on Transaction, which is often created on success only).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.core.cache import cache
from django.db.models import Count, QuerySet
from django.utils import timezone

from apps.bbps.models import BillPayment
from apps.fund_management.models import LoadMoney, Payout

VALID_MODULES = frozenset({'all', 'payin', 'payout', 'bbps'})
VALID_INTERVALS = frozenset({'daily', 'monthly', 'yearly'})
STATUS_KEYS = ('PENDING', 'SUCCESS', 'FAILED')
MAX_PERIOD_DAYS = 366

CACHE_KEY_PREFIX = 'dashboard_txn_status_v1'
CACHE_TTL_SECONDS = 12

MODULE_REGISTRY: dict[str, dict[str, Any]] = {
    'payin': {'model': LoadMoney, 'label': 'Pay-in'},
    'payout': {'model': Payout, 'label': 'Payout'},
    'bbps': {'model': BillPayment, 'label': 'BBPS'},
}


def _empty_counts() -> dict[str, int]:
    return {k: 0 for k in STATUS_KEYS} | {'total': 0}


def normalize_status(raw: str | None) -> str:
    st = (raw or 'PENDING').strip().upper()
    if st == 'FAILURE':
        st = 'FAILED'
    if st not in STATUS_KEYS:
        return 'PENDING'
    return st


def count_status_for_queryset(qs: QuerySet) -> dict[str, int]:
    """Single aggregation query: counts by status."""
    out = _empty_counts()
    for row in qs.values('status').annotate(n=Count('id')).order_by():
        key = normalize_status(row.get('status'))
        n = int(row.get('n') or 0)
        out[key] += n
        out['total'] += n
    return out


def _merge_counts(*parts: dict[str, int]) -> dict[str, int]:
    merged = _empty_counts()
    for part in parts:
        for k in STATUS_KEYS:
            merged[k] += int(part.get(k, 0))
        merged['total'] += int(part.get('total', 0))
    return merged


def _local_today() -> date:
    return timezone.localdate()


def resolve_period(
    interval: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[date, date, str]:
    """
    Resolve inclusive date range and normalized interval.
    Defaults use Asia/Kolkata via timezone.localdate().
    """
    interval = (interval or 'daily').strip().lower()
    if interval not in VALID_INTERVALS:
        interval = 'daily'

    today = _local_today()

    if date_from is None and date_to is None:
        if interval == 'daily':
            date_from = date_to = today
        elif interval == 'monthly':
            date_from = today.replace(day=1)
            date_to = today
        else:
            date_from = today.replace(month=1, day=1)
            date_to = today
    elif date_from is None:
        date_from = date_to
    elif date_to is None:
        date_to = date_from

    if date_from > date_to:
        date_from, date_to = date_to, date_from

    span = (date_to - date_from).days + 1
    if span > MAX_PERIOD_DAYS:
        date_from = date_to - timedelta(days=MAX_PERIOD_DAYS - 1)

    return date_from, date_to, interval


def _base_qs(model) -> QuerySet:
    return model.objects.filter(is_deleted=False)


def _filter_period(qs: QuerySet, date_from: date, date_to: date) -> QuerySet:
    return qs.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )


def counts_for_module_key(module_key: str, date_from: date, date_to: date) -> dict[str, int]:
    entry = MODULE_REGISTRY[module_key]
    qs = _filter_period(_base_qs(entry['model']), date_from, date_to)
    return count_status_for_queryset(qs)


def aggregate_module_counts(
    module: str,
    date_from: date,
    date_to: date,
) -> tuple[dict[str, int], dict[str, dict[str, int]] | None]:
    module = (module or 'all').strip().lower()
    if module not in VALID_MODULES:
        module = 'all'

    by_module: dict[str, dict[str, int]] = {}
    if module == 'all':
        for key in MODULE_REGISTRY:
            by_module[key] = counts_for_module_key(key, date_from, date_to)
        totals = _merge_counts(*by_module.values())
        return totals, by_module

    totals = counts_for_module_key(module, date_from, date_to)
    return totals, None


def _cache_key(module: str, interval: str, date_from: date, date_to: date) -> str:
    return f'{CACHE_KEY_PREFIX}:{module}:{interval}:{date_from.isoformat()}:{date_to.isoformat()}'


def get_dashboard_transaction_status(
    *,
    module: str = 'all',
    interval: str = 'daily',
    date_from_raw: str | None = None,
    date_to_raw: str | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Build API payload for admin dashboard transaction status overview."""
    df = parse_date_param(date_from_raw)
    dt = parse_date_param(date_to_raw)
    date_from, date_to, interval = resolve_period(interval, df, dt)
    module = (module or 'all').strip().lower()
    if module not in VALID_MODULES:
        module = 'all'

    cache_key = _cache_key(module, interval, date_from, date_to)
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    counts, by_module = aggregate_module_counts(module, date_from, date_to)

    payload: dict[str, Any] = {
        'module': module,
        'interval': interval,
        'period': {
            'from': date_from.isoformat(),
            'to': date_to.isoformat(),
        },
        'counts': counts,
    }
    if by_module is not None:
        payload['by_module'] = by_module

    if use_cache:
        cache.set(cache_key, payload, CACHE_TTL_SECONDS)

    return payload


def parse_date_param(raw: str | None) -> date | None:
    if not raw or not str(raw).strip():
        return None
    from django.utils.dateparse import parse_date

    parsed = parse_date(str(raw).strip())
    return parsed
