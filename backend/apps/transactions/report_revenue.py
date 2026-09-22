"""
Unified Revenue & Commission report API.

GET /api/reports/revenue/
GET /api/reports/revenue/summary/
GET /api/reports/revenue/breakdown/<service_id>/
GET /api/reports/revenue/export.csv
GET /api/reports/revenue/unattributed/  (admin)
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.roles import is_platform_operator
from apps.transactions.models import CommissionLedger
from apps.transactions.report_filters import apply_commission_ledger_filters
from apps.transactions.reporting_scope import (
    commission_ledger_q_for_team,
    get_report_scope,
)
from apps.transactions.serializers import CommissionLedgerSerializer
from apps.transactions.services.fee_settlement import unattributed_revenue_queryset
from apps.wallets.models import Wallet


def _page_params(request):
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(100, max(1, int(request.query_params.get('page_size', 25))))
    except (TypeError, ValueError):
        page_size = 25
    return page, page_size


def _base_ledger_qs(request):
    try:
        ledger_extra = commission_ledger_q_for_team(request)
    except PermissionDenied:
        raise
    from apps.fund_management.platform_settlement import ledger_user_for_viewer

    owner = ledger_user_for_viewer(request.user)
    qs = (
        CommissionLedger.objects.filter(user=owner)
        .filter(ledger_extra)
        .order_by('-created_at')
    )
    qs = apply_commission_ledger_filters(qs, request)

    module = (request.query_params.get('module') or '').strip().lower()
    if module == 'payin':
        qs = qs.filter(Q(module='payin') | Q(source__in=('payin', 'profit')))
    elif module:
        qs = qs.filter(Q(module=module) | Q(source=module))

    entry_kind = (request.query_params.get('entry_kind') or request.query_params.get('type') or '').strip().lower()
    if entry_kind in ('commission', 'service_fee'):
        qs = qs.filter(entry_kind=entry_kind)

    return qs.order_by('-created_at')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_report_view(request):
    """GET /api/reports/revenue/"""
    try:
        qs = _base_ledger_qs(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(getattr(e, 'detail', e)), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )

    page, page_size = _page_params(request)
    total = qs.count()
    start = (page - 1) * page_size
    rows = list(qs[start:start + page_size])
    ledger_total = qs.aggregate(s=Coalesce(Sum('amount'), Decimal('0')))['s'] or Decimal('0')

    from apps.fund_management.platform_settlement import wallet_user_for_viewer

    wallet_owner = wallet_user_for_viewer(request.user)
    main = Wallet.objects.filter(user=wallet_owner, wallet_type='main').first()
    main_balance = main.balance if main else Decimal('0')

    return Response({
        'success': True,
        'data': {
            'ledger': CommissionLedgerSerializer(
                rows, many=True, context={'request': request}
            ).data,
            'scope': get_report_scope(request),
            'total': total,
            'page': page,
            'page_size': page_size,
            'summary': {
                'ledger_total': str(ledger_total),
                'total_commission': str(ledger_total),
                'current_balance': str(main_balance),
                'ledger_count': total,
            },
        },
        'message': 'Revenue report retrieved',
        'errors': [],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_summary_view(request):
    """GET /api/reports/revenue/summary/ — metric tiles."""
    # Optional interval=day|month|year when date_from/date_to omitted.
    interval_raw = (request.query_params.get('interval') or '').strip().lower()
    if interval_raw in ('day', 'daily', 'month', 'monthly', 'year', 'yearly') and not (
        (request.query_params.get('date_from') or '').strip()
        or (request.query_params.get('date_to') or '').strip()
    ):
        from apps.transactions.dashboard_stats import resolve_period

        mapped = {
            'day': 'daily',
            'daily': 'daily',
            'month': 'monthly',
            'monthly': 'monthly',
            'year': 'yearly',
            'yearly': 'yearly',
        }[interval_raw]
        df, dt, _ = resolve_period(mapped)
        # Mutate a copy of query params for filter helpers
        mutable = request.query_params.copy()
        mutable['date_from'] = df.isoformat()
        mutable['date_to'] = dt.isoformat()

        class _Req:
            user = request.user
            query_params = mutable

        request = _Req()  # noqa: PLW2901 — scoped to this view

    try:
        qs = _base_ledger_qs(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(getattr(e, 'detail', e)), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )

    total = qs.aggregate(s=Coalesce(Sum('amount'), Decimal('0')))['s'] or Decimal('0')
    commission = qs.filter(entry_kind='commission').aggregate(
        s=Coalesce(Sum('amount'), Decimal('0'))
    )['s'] or Decimal('0')
    service_fees = qs.filter(entry_kind='service_fee').aggregate(
        s=Coalesce(Sum('amount'), Decimal('0'))
    )['s'] or Decimal('0')

    by_module = {}
    for row in qs.values('module', 'source').annotate(
        total=Coalesce(Sum('amount'), Decimal('0')),
        count=Count('id'),
    ):
        key = (row['module'] or row['source'] or 'other').lower()
        if key == 'profit':
            key = 'payin'
        bucket = by_module.setdefault(key, {'total': Decimal('0'), 'count': 0})
        bucket['total'] += row['total'] or Decimal('0')
        bucket['count'] += int(row['count'] or 0)

    return Response({
        'success': True,
        'data': {
            'total_earned': str(total),
            'commission': str(commission),
            'service_fees': str(service_fees),
            'by_module': {
                k: {'total': str(v['total']), 'count': v['count']}
                for k, v in sorted(by_module.items())
            },
            'scope': get_report_scope(request),
        },
        'message': 'Revenue summary retrieved',
        'errors': [],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_breakdown_view(request, service_id: str):
    """
    GET /api/reports/revenue/breakdown/<service_id>/

    Platform operators: full split (every beneficiary).
    Channel roles: own credit only — no peer amounts / commission structure.
    """
    sid = (service_id or '').strip()
    if not sid:
        return Response(
            {'success': False, 'data': None, 'message': 'service_id required', 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )

    rows = list(
        CommissionLedger.objects.filter(reference_service_id=sid)
        .select_related('user')
        .order_by('created_at', 'id')
    )
    if not rows:
        return Response(
            {'success': False, 'data': None, 'message': 'No ledger rows for this reference', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )

    viewer = request.user
    is_operator = is_platform_operator(getattr(viewer, 'role', ''))

    # Visibility: requester must own a slice, or be platform operator / team scope.
    owned = any(r.user_id == viewer.pk for r in rows)
    if not owned and not is_operator:
        try:
            extra = commission_ledger_q_for_team(request)
            if not CommissionLedger.objects.filter(reference_service_id=sid).filter(extra).exists():
                return Response(
                    {'success': False, 'data': None, 'message': 'Not permitted', 'errors': []},
                    status=status.HTTP_403_FORBIDDEN,
                )
        except PermissionDenied:
            return Response(
                {'success': False, 'data': None, 'message': 'Not permitted', 'errors': []},
                status=status.HTTP_403_FORBIDDEN,
            )

    if not is_operator:
        own_rows = [r for r in rows if r.user_id == viewer.pk]
        if not own_rows:
            return Response(
                {'success': False, 'data': None, 'message': 'Not permitted', 'errors': []},
                status=status.HTTP_403_FORBIDDEN,
            )
        my_share = sum((r.amount or Decimal('0') for r in own_rows), Decimal('0'))
        first = own_rows[0]
        return Response({
            'success': True,
            'data': {
                'reference_service_id': sid,
                'full_split': False,
                'my_share': str(my_share),
                'entry_kind': first.entry_kind,
                'module': first.module or first.source,
                'source': first.source,
                'created_at': first.created_at,
                'slice_count': 0,
                'slices': [],
            },
            'message': 'Earnings detail retrieved',
            'errors': [],
        })

    customer_charge = rows[0].customer_charge or Decimal('0')
    if not customer_charge:
        customer_charge = sum(
            (r.amount for r in rows if (r.slice_key or '') and not str(r.slice_key).endswith('_reversal')),
            Decimal('0'),
        )

    slices = []
    for r in rows:
        slices.append({
            'id': r.pk,
            'beneficiary_user_id': r.user_id,
            'beneficiary_code': getattr(r.user, 'user_id', None) if r.user_id else None,
            'beneficiary_role': r.role_at_time,
            'amount': str(r.amount),
            'slice_key': r.slice_key or (r.meta or {}).get('slice') or '',
            'entry_kind': r.entry_kind,
            'module': r.module or r.source,
            'source': r.source,
            'created_at': r.created_at,
            'source_user_code': r.source_user_code,
            'source_role': r.source_role,
            'source_name': r.source_name_snapshot,
        })

    return Response({
        'success': True,
        'data': {
            'reference_service_id': sid,
            'full_split': True,
            'customer_charge': str(customer_charge),
            'slice_count': len(slices),
            'slices': slices,
        },
        'message': 'Breakdown retrieved',
        'errors': [],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_export_csv(request):
    """GET /api/reports/revenue/export.csv"""
    try:
        qs = _base_ledger_qs(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(getattr(e, 'detail', e)), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )

    import csv
    from io import StringIO

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'DATE', 'REFERENCE', 'MODULE', 'TYPE', 'SLICE',
        'SOURCE_USER', 'SOURCE_ROLE', 'CUSTOMER_CHARGE', 'MY_SHARE', 'STATUS',
    ])
    for r in qs[:10000]:
        writer.writerow([
            r.created_at.isoformat() if r.created_at else '',
            r.reference_service_id,
            r.module or r.source,
            r.entry_kind,
            r.slice_key or (r.meta or {}).get('slice') or '',
            r.source_name_snapshot or r.source_user_code,
            r.source_role,
            str(r.customer_charge or '') if is_platform_operator(getattr(request.user, 'role', '')) else '',
            str(r.amount),
            'SUCCESS',
        ])

    resp = HttpResponse(buf.getvalue(), content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="revenue_report.csv"'
    return resp


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unattributed_revenue_view(request):
    """GET /api/reports/revenue/unattributed/ — platform operator only."""
    if not is_platform_operator(getattr(request.user, 'role', '')):
        return Response(
            {'success': False, 'data': None, 'message': 'Admin only', 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    qs = unattributed_revenue_queryset().order_by('-created_at')
    page, page_size = _page_params(request)
    total = qs.count()
    start = (page - 1) * page_size
    rows = list(qs[start:start + page_size])
    return Response({
        'success': True,
        'data': {
            'ledger': CommissionLedgerSerializer(
                rows, many=True, context={'request': request}
            ).data,
            'total': total,
            'page': page,
            'page_size': page_size,
        },
        'message': 'Unattributed revenue retrieved',
        'errors': [],
    })
