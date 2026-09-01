"""
Admin gateway sales & profit analytics — platform-wide aggregates from LoadMoney.

All users' successful pay-ins are included (not scoped to the admin account or scope=self).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.cache import cache
from django.db.models import Case, CharField, Count, F, Sum, Value, When
from django.db.models.functions import Coalesce, NullIf, Replace, TruncDate, TruncMonth

from apps.admin_panel.models import PaymentGateway
from apps.fund_management.models import LoadMoney
from apps.transactions.dashboard_stats import parse_date_param, resolve_period
from apps.transactions.models import CommissionLedger

CACHE_KEY_PREFIX = 'gateway_analytics_v1'
CACHE_TTL_SECONDS = 60

_EMPTY = Value('')


def _gateway_label_expression():
    """SQL equivalent of payin_collection_method_label (QR account vs gateway provider)."""
    qr_name = Coalesce(
        NullIf(F('pay_in_qr_account__display_name'), _EMPTY),
        NullIf(F('gateway'), _EMPTY),
        Value('Manual QR'),
        output_field=CharField(),
    )
    pkg_provider_name = Case(
        When(package__provider__iexact='razorpay', then=Value('Razorpay')),
        When(package__provider__iexact='payu', then=Value('PayU')),
        When(package__provider__iexact='mock', then=Value('Mock (test)')),
        default=Value(''),
        output_field=CharField(),
    )
    gateway_fallback = Replace(
        Coalesce(NullIf(F('gateway'), _EMPTY), Value('Unknown')),
        Value('_'),
        Value(' '),
    )
    gw_name = Coalesce(
        NullIf(F('payment_gateway__name'), _EMPTY),
        NullIf(F('package__payment_gateway__name'), _EMPTY),
        NullIf(pkg_provider_name, _EMPTY),
        NullIf(F('package__display_name'), _EMPTY),
        NullIf(F('package__code'), _EMPTY),
        gateway_fallback,
        output_field=CharField(),
    )
    return Case(
        When(collection_rail='qr', then=qr_name),
        default=gw_name,
        output_field=CharField(),
    )


def _format_period_bucket(bucket, interval: str) -> str:
    if bucket is None:
        return ''
    if interval == 'monthly':
        return bucket.strftime('%Y-%m')
    if hasattr(bucket, 'date') and callable(bucket.date):
        try:
            return bucket.date().isoformat()
        except (ValueError, OverflowError):
            pass
    if hasattr(bucket, 'isoformat'):
        text = bucket.isoformat()
        return text[:10] if len(text) >= 10 else text
    return str(bucket)


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

    period_expr = TruncMonth('created_at') if interval == 'monthly' else TruncDate('created_at')
    base = (
        LoadMoney.objects.filter(is_deleted=False, status='SUCCESS')
        .filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )
        .annotate(
            period_bucket=period_expr,
            gateway_name=_gateway_label_expression(),
        )
    )
    if gateway_filter:
        base = base.filter(gateway_name__iexact=gateway_filter)

    aggregated = list(
        base.values('period_bucket', 'gateway_name')
        .annotate(
            payin_sales=Sum('amount'),
            payin_charges=Sum('charge'),
            transactions_count=Count('id'),
        )
        .order_by('period_bucket', 'gateway_name')
    )

    profit_by_bucket: dict[tuple[str, str], Decimal] = {}
    tid_rows = base.values_list('transaction_id', 'period_bucket', 'gateway_name')
    service_ids = []
    tid_to_bucket: dict[str, tuple[str, str]] = {}
    for tid, bucket, gw in tid_rows:
        if not tid:
            continue
        service_ids.append(tid)
        period = _format_period_bucket(bucket, interval)
        tid_to_bucket[str(tid)] = (period, str(gw or 'Unknown'))

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
            key = tid_to_bucket.get(str(row['reference_service_id'] or ''))
            if not key:
                continue
            profit_by_bucket[key] = profit_by_bucket.get(key, Decimal('0')) + (row['total'] or Decimal('0'))

    rows = []
    grand = {
        'payin_sales': Decimal('0'),
        'payin_charges': Decimal('0'),
        'platform_profit': Decimal('0'),
        'transactions_count': 0,
    }
    for row in aggregated:
        period = _format_period_bucket(row['period_bucket'], interval)
        gateway = str(row['gateway_name'] or 'Unknown')
        sales = row['payin_sales'] or Decimal('0')
        charges = row['payin_charges'] or Decimal('0')
        count = int(row['transactions_count'] or 0)
        profit = profit_by_bucket.get((period, gateway), Decimal('0'))
        rows.append(
            {
                'period': period,
                'gateway': gateway,
                'payin_sales': str(sales),
                'payin_charges': str(charges),
                'platform_profit': str(profit),
                'transactions_count': count,
            }
        )
        grand['payin_sales'] += sales
        grand['payin_charges'] += charges
        grand['platform_profit'] += profit
        grand['transactions_count'] += count

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
