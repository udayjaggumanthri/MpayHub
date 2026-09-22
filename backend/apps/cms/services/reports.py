"""CMS-only reports (never joins AEPS or shared Transaction)."""
from __future__ import annotations

import csv
import io
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.cms.models import CmsTransaction, CmsWalletEntry


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
    qs = CmsTransaction.objects.filter(is_deleted=False).select_related('user', 'agent')
    if not admin_all:
        qs = qs.filter(user=user)
    return qs


def serialize_txn(txn: CmsTransaction) -> dict:
    return {
        'id': txn.pk,
        'merchant_transaction_id': txn.merchant_transaction_id,
        'fp_transaction_id': txn.fp_transaction_id,
        'type_of_transaction': txn.type_of_transaction,
        'product_label': 'Cash Collection' if txn.type_of_transaction == 'CDC' else txn.type_of_transaction,
        'status': txn.status,
        'amount': str(txn.amount),
        'bc_login_id': txn.bc_login_id,
        'agent_login_id': txn.agent_login_id,
        'drop_amount': str(txn.drop_amount) if txn.drop_amount is not None else None,
        'error_message': txn.error_message,
        'remarks': txn.remarks,
        'initiated_at': txn.initiated_at.isoformat() if txn.initiated_at else None,
        'finalized_at': txn.finalized_at.isoformat() if txn.finalized_at else None,
        'created_at': txn.created_at.isoformat() if txn.created_at else None,
        'user_id': txn.user_id,
        'user_name': getattr(txn.user, 'full_name', None) or getattr(txn.user, 'phone', ''),
    }


def query_transactions(
    *,
    user=None,
    admin_all: bool = False,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    qs = _base_qs(user=user, admin_all=admin_all)
    if status:
        qs = qs.filter(status=status.lower())
    start, end = _parse_day_bounds(date_from, date_to)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)
    if search:
        qs = qs.filter(
            Q(merchant_transaction_id__icontains=search)
            | Q(fp_transaction_id__icontains=search)
            | Q(bc_login_id__icontains=search)
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
    days: int = 30,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
) -> dict:
    qs = _base_qs(user=user, admin_all=admin_all)
    start, end = _parse_day_bounds(date_from, date_to)
    if start or end:
        if start:
            qs = qs.filter(created_at__gte=start)
        if end:
            qs = qs.filter(created_at__lte=end)
    else:
        since = timezone.now() - timedelta(days=max(1, int(days or 30)))
        qs = qs.filter(created_at__gte=since)
    if status:
        qs = qs.filter(status=status.lower())

    total = qs.count()
    by_status = {r['status']: r['c'] for r in qs.values('status').annotate(c=Count('id'))}
    volume = qs.filter(status='success').aggregate(v=Sum('amount'))['v'] or Decimal('0')
    return {
        'total': total,
        'success': by_status.get('success', 0),
        'failed': by_status.get('failed', 0),
        'initiated': by_status.get('initiated', 0),
        'expired': by_status.get('expired', 0),
        'volume': str(volume),
    }


def export_transactions_csv(
    *,
    user=None,
    admin_all: bool = False,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    limit: int = 5000,
) -> HttpResponse:
    data = query_transactions(
        user=user,
        admin_all=admin_all,
        status=status,
        date_from=date_from,
        date_to=date_to,
        search=search,
        limit=limit,
        offset=0,
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            'when',
            'status',
            'amount',
            'fp_transaction_id',
            'merchant_transaction_id',
            'bc_login_id',
            'type',
            'error_message',
        ]
    )
    for r in data['results']:
        writer.writerow(
            [
                r.get('created_at') or '',
                r.get('status') or '',
                r.get('amount') or '',
                r.get('fp_transaction_id') or '',
                r.get('merchant_transaction_id') or '',
                r.get('bc_login_id') or '',
                r.get('type_of_transaction') or '',
                r.get('error_message') or '',
            ]
        )
    resp = HttpResponse(buf.getvalue(), content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="cms-reports.csv"'
    return resp


def list_wallet_entries(*, user, limit: int = 50) -> list[dict]:
    from apps.cms.services.wallet import get_or_create_wallet

    wallet = get_or_create_wallet(user)
    rows = CmsWalletEntry.objects.filter(wallet=wallet).order_by('-created_at')[:limit]
    return [
        {
            'id': e.pk,
            'entry_type': e.entry_type,
            'amount': str(e.amount),
            'opening_balance': str(e.opening_balance),
            'closing_balance': str(e.closing_balance),
            'reference': e.reference,
            'description': e.description,
            'created_at': e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]
