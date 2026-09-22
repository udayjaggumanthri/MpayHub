"""AEPS-only reports (never joins shared Transaction/Passbook)."""
from __future__ import annotations

import csv
import io
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.aeps.models import AepsTransaction
from apps.aeps.services.products import PRODUCT_LABELS, serialize_txn


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


def _base_qs(*, user=None, admin_all: bool = False):
    qs = AepsTransaction.objects.filter(is_deleted=False).select_related('user', 'merchant')
    if not admin_all:
        qs = qs.filter(user=user)
    return qs


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
    qs = _base_qs(user=user, admin_all=admin_all)
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


def summary_stats(
    *,
    user=None,
    admin_all: bool = False,
    days: int = 7,
    date_from: str | None = None,
    date_to: str | None = None,
    product: str | None = None,
    status: str | None = None,
) -> dict:
    qs = _base_qs(user=user, admin_all=admin_all)
    start, end = _parse_day_bounds(date_from, date_to)
    if start or end:
        if start:
            qs = qs.filter(created_at__gte=start)
        if end:
            qs = qs.filter(created_at__lte=end)
        window_days = None
    else:
        window_days = max(1, int(days or 7))
        since = timezone.now() - timedelta(days=window_days)
        qs = qs.filter(created_at__gte=since)
    if product:
        qs = qs.filter(product=product.upper())
    if status:
        qs = qs.filter(status=status.lower())
    agg = qs.aggregate(
        total=Count('id'),
        success=Count('id', filter=Q(status__in=['success', 'reconciled'])),
        failed=Count('id', filter=Q(status='failed')),
        pending=Count('id', filter=Q(status__in=['pending', 'initiated', 'timeout'])),
        volume=Sum('amount', filter=Q(status__in=['success', 'reconciled'])),
    )
    by_product = [
        {
            'product': row['product'],
            'label': PRODUCT_LABELS.get(row['product'], row['product']),
            'count': row['c'],
        }
        for row in qs.values('product').annotate(c=Count('id')).order_by('product')
    ]
    return {
        'days': window_days,
        'date_from': date_from or '',
        'date_to': date_to or '',
        'total': agg['total'] or 0,
        'success': agg['success'] or 0,
        'failed': agg['failed'] or 0,
        'pending': agg['pending'] or 0,
        'volume': str(agg['volume'] or Decimal('0')),
        'by_product': by_product,
    }


def export_transactions_csv(
    *,
    user=None,
    admin_all: bool = False,
    product: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    limit: int = 5000,
) -> HttpResponse:
    data = query_transactions(
        user=user,
        admin_all=admin_all,
        product=product,
        status=status,
        date_from=date_from,
        date_to=date_to,
        search=search,
        limit=min(max(1, limit), 10000),
        offset=0,
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            'created_at',
            'product',
            'status',
            'amount',
            'bank_rrn',
            'merchant_tran_id',
            'fp_transaction_id',
            'bank_name',
            'bank_iin',
            'masked_aadhaar',
            'response_code',
            'response_message',
            'balance_amount',
            'acknowledged',
        ]
    )
    for r in data['results']:
        writer.writerow(
            [
                r.get('created_at') or '',
                r.get('product') or '',
                r.get('status') or '',
                r.get('amount') or '',
                r.get('bank_rrn') or '',
                r.get('merchant_tran_id') or '',
                r.get('fp_transaction_id') or '',
                r.get('bank_name') or '',
                r.get('bank_iin') or '',
                r.get('masked_aadhaar') or '',
                r.get('response_code') or '',
                (r.get('response_message') or '').replace('\n', ' ')[:500],
                r.get('balance_amount') or '',
                'yes' if r.get('acknowledged') else 'no',
            ]
        )
    resp = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="aeps-transactions.csv"'
    return resp
