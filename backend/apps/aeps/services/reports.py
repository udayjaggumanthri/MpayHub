"""AEPS-only reports (never joins shared Transaction/Passbook)."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.aeps.models import AepsTransaction
from apps.aeps.services.products import serialize_txn


def _parse_day_bounds(date_from: str | None, date_to: str | None):
    tz = timezone.get_current_timezone()
    start = None
    end = None
    if date_from:
        d = parse_date(date_from)
        if d:
            start = timezone.make_aware(datetime.combine(d, time.min), tz)
    if date_to:
        d = parse_date(date_to)
        if d:
            end = timezone.make_aware(datetime.combine(d, time.max), tz)
    return start, end


def query_transactions(
    *,
    user=None,
    admin_all: bool = False,
    product: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    qs = AepsTransaction.objects.filter(is_deleted=False).select_related('user', 'merchant')
    if not admin_all:
        qs = qs.filter(user=user)
    if product:
        qs = qs.filter(product=product.upper())
    if status:
        qs = qs.filter(status=status.lower())
    start, end = _parse_day_bounds(date_from, date_to)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)
    if search:
        qs = qs.filter(
            Q(merchant_tran_id__icontains=search)
            | Q(bank_rrn__icontains=search)
            | Q(fp_transaction_id__icontains=search)
            | Q(masked_aadhaar__icontains=search)
        )
    total = qs.count()
    rows = list(qs.order_by('-created_at')[offset : offset + limit])
    return {
        'total': total,
        'limit': limit,
        'offset': offset,
        'results': [serialize_txn(r) for r in rows],
    }


def summary_stats(*, user=None, admin_all: bool = False, days: int = 7) -> dict:
    since = timezone.now() - timedelta(days=max(1, days))
    qs = AepsTransaction.objects.filter(is_deleted=False, created_at__gte=since)
    if not admin_all:
        qs = qs.filter(user=user)
    agg = qs.aggregate(
        total=Count('id'),
        success=Count('id', filter=Q(status__in=['success', 'reconciled'])),
        failed=Count('id', filter=Q(status='failed')),
        pending=Count('id', filter=Q(status__in=['pending', 'initiated', 'timeout'])),
        volume=Sum('amount', filter=Q(status__in=['success', 'reconciled'])),
    )
    by_product = list(
        qs.values('product').annotate(c=Count('id')).order_by('product')
    )
    return {
        'days': days,
        'total': agg['total'] or 0,
        'success': agg['success'] or 0,
        'failed': agg['failed'] or 0,
        'pending': agg['pending'] or 0,
        'volume': str(agg['volume'] or Decimal('0')),
        'by_product': by_product,
    }
