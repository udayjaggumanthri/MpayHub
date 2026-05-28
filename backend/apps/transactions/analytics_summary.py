"""
Admin gateway sales & profit analytics — platform-wide aggregates from LoadMoney.

All users' successful pay-ins are included (not scoped to the admin account or scope=self).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.cache import cache
from django.db.models import Sum

from apps.admin_panel.models import PaymentGateway
from apps.fund_management.models import LoadMoney
from apps.fund_management.serializers import payin_payment_gateway_name
from apps.transactions.dashboard_stats import parse_date_param, resolve_period
from apps.transactions.models import CommissionLedger

CACHE_KEY_PREFIX = 'gateway_analytics_v1'
CACHE_TTL_SECONDS = 12


def _gateway_name(lm: LoadMoney) -> str:
    name = (payin_payment_gateway_name(lm) or '').strip()
    if not name or name == '—':
        name = str(lm.gateway or 'unknown').replace('_', ' ').strip() or 'Unknown'
    return name


def _period_key(created_at, interval: str) -> str:
    if interval == 'monthly':
        return created_at.strftime('%Y-%m')
    return created_at.date().isoformat()


def get_gateway_analytics_summary(
    *,
    interval: str = 'daily',
    date_from_raw: str | None = None,
    date_to_raw: str | None = None,
    gateway_filter: str = '',
    use_cache: bool = True,
) -> dict[str, Any]:
    """
    Platform-wide SUCCESS pay-in sales, charges, and platform profit by gateway and period.
    """
    interval = (interval or 'daily').strip().lower()
    if interval not in ('daily', 'monthly'):
        interval = 'daily'

    df = parse_date_param(date_from_raw)
    dt = parse_date_param(date_to_raw)
    date_from, date_to, _ = resolve_period(interval, df, dt)

    gateway_filter = (gateway_filter or '').strip().lower()
    cache_key = f'{CACHE_KEY_PREFIX}:{interval}:{date_from}:{date_to}:{gateway_filter}'
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    lm_qs = (
        LoadMoney.objects.filter(is_deleted=False, status='SUCCESS')
        .filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )
        .select_related('payment_gateway', 'package__payment_gateway')
        .order_by('created_at')
    )

    service_ids = list(lm_qs.values_list('transaction_id', flat=True))
    profit_by_service: dict[str, Decimal] = {}
    if service_ids:
        for row in (
            CommissionLedger.objects.filter(
                is_deleted=False,
                source='profit',
                reference_service_id__in=service_ids,
            )
            .values('reference_service_id')
            .annotate(total=Sum('amount'))
        ):
            profit_by_service[row['reference_service_id']] = row['total'] or Decimal('0')

    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for lm in lm_qs:
        gateway = _gateway_name(lm)
        if gateway_filter and gateway_filter != gateway.lower():
            continue
        period = _period_key(lm.created_at, interval)
        key = (period, gateway)
        if key not in buckets:
            buckets[key] = {
                'period': period,
                'gateway': gateway,
                'payin_sales': Decimal('0'),
                'payin_charges': Decimal('0'),
                'platform_profit': Decimal('0'),
                'transactions_count': 0,
            }
        buckets[key]['payin_sales'] += lm.amount or Decimal('0')
        buckets[key]['payin_charges'] += lm.charge or Decimal('0')
        buckets[key]['platform_profit'] += profit_by_service.get(lm.transaction_id, Decimal('0'))
        buckets[key]['transactions_count'] += 1

    rows = []
    grand = {
        'payin_sales': Decimal('0'),
        'payin_charges': Decimal('0'),
        'platform_profit': Decimal('0'),
        'transactions_count': 0,
    }
    for key in sorted(buckets.keys()):
        row = buckets[key]
        rows.append(
            {
                'period': row['period'],
                'gateway': row['gateway'],
                'payin_sales': str(row['payin_sales']),
                'payin_charges': str(row['payin_charges']),
                'platform_profit': str(row['platform_profit']),
                'transactions_count': row['transactions_count'],
            }
        )
        grand['payin_sales'] += row['payin_sales']
        grand['payin_charges'] += row['payin_charges']
        grand['platform_profit'] += row['platform_profit']
        grand['transactions_count'] += row['transactions_count']

    configured_gateways = list(
        PaymentGateway.objects.filter(is_deleted=False, status='active')
        .order_by('name')
        .values_list('name', flat=True)
    )
    gateways = sorted(set(configured_gateways) | {r['gateway'] for r in rows})

    payload = {
        'interval': interval,
        'period': {'from': date_from.isoformat(), 'to': date_to.isoformat()},
        'scope': 'platform',
        'rows': rows,
        'available_gateways': gateways,
        'totals': {
            'payin_sales': str(grand['payin_sales']),
            'payin_charges': str(grand['payin_charges']),
            'platform_profit': str(grand['platform_profit']),
            'transactions_count': grand['transactions_count'],
        },
    }

    if use_cache:
        cache.set(cache_key, payload, CACHE_TTL_SECONDS)

    return payload
