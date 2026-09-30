"""
Admin payout recovery APIs — stuck PENDING queue + manual SUCCESS/FAILED.
"""
from __future__ import annotations

from django.db.models import Q

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from apps.core.permissions import IsAdmin
from apps.fund_management.models import Payout
from apps.fund_management.payout_reconcile import (
    DEFAULT_STUCK_MINUTES,
    admin_mark_payout_failed,
    admin_mark_payout_success,
    pending_payout_queryset,
    payout_recovery_stats,
    serialize_payout_recovery_row,
)


def _err(exc, fallback='Invalid request'):
    detail = getattr(exc, 'detail', None)
    if isinstance(detail, dict):
        first = next(iter(detail.values()), None)
        if isinstance(first, (list, tuple)) and first:
            msg = str(first[0])
        else:
            msg = str(first or fallback)
        return Response(
            {'success': False, 'data': None, 'message': msg, 'errors': detail},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {'success': False, 'data': None, 'message': str(detail or exc or fallback), 'errors': []},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def payout_recovery_stats_view(request):
    try:
        stuck = int(request.query_params.get('stuck_minutes') or DEFAULT_STUCK_MINUTES)
    except (TypeError, ValueError):
        stuck = DEFAULT_STUCK_MINUTES
    data = payout_recovery_stats(stuck_minutes=stuck)
    return Response(
        {
            'success': True,
            'data': data,
            'message': 'OK',
            'errors': [],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def payout_recovery_list_view(request):
    q = (request.query_params.get('q') or '').strip()
    try:
        min_age = int(request.query_params.get('min_age_minutes') or 0)
    except (TypeError, ValueError):
        min_age = 0
    try:
        page_size = int(request.query_params.get('page_size') or 20)
    except (TypeError, ValueError):
        page_size = 20
    page_size = max(1, min(page_size, 100))
    try:
        page = int(request.query_params.get('page') or 1)
    except (TypeError, ValueError):
        page = 1
    page = max(1, page)

    qs = pending_payout_queryset(min_age_minutes=min_age if min_age > 0 else None)
    if q:
        qs = qs.filter(
            Q(transaction_id__icontains=q)
            | Q(merchant_ref_id__icontains=q)
            | Q(provider_txn_id__icontains=q)
            | Q(user__phone__icontains=q)
            | Q(user__user_id__icontains=q)
            | Q(rrn__icontains=q)
        )

    total = qs.count()
    start = (page - 1) * page_size
    rows = [serialize_payout_recovery_row(p) for p in qs[start : start + page_size]]
    return Response(
        {
            'success': True,
            'data': {
                'results': rows,
                'total': total,
                'page': page,
                'page_size': page_size,
            },
            'message': 'OK',
            'errors': [],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def payout_recovery_detail_view(request, pk: int):
    payout = (
        Payout.objects.filter(pk=pk, is_deleted=False)
        .select_related('user', 'bank_account')
        .first()
    )
    if not payout:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    data = serialize_payout_recovery_row(payout)
    data['failure_reason'] = payout.failure_reason or ''
    data['response_meta'] = payout.response_meta if isinstance(payout.response_meta, dict) else {}
    return Response({'success': True, 'data': data, 'message': 'OK', 'errors': []})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def payout_recovery_mark_success_view(request, pk: int):
    payout = Payout.objects.filter(pk=pk, is_deleted=False).first()
    if not payout:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        updated = admin_mark_payout_success(
            payout=payout,
            actor=request.user,
            rrn=str(request.data.get('rrn') or ''),
            provider_txn_id=str(request.data.get('provider_txn_id') or ''),
            internal_note=str(request.data.get('internal_note') or ''),
        )
    except ValidationError as exc:
        return _err(exc, 'Could not mark SUCCESS')
    return Response(
        {
            'success': True,
            'data': serialize_payout_recovery_row(updated),
            'message': 'Marked SUCCESS and settled hold',
            'errors': [],
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def payout_recovery_mark_failed_view(request, pk: int):
    payout = Payout.objects.filter(pk=pk, is_deleted=False).first()
    if not payout:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        updated = admin_mark_payout_failed(
            payout=payout,
            actor=request.user,
            reason=str(request.data.get('reason') or ''),
            internal_note=str(request.data.get('internal_note') or ''),
        )
    except ValidationError as exc:
        return _err(exc, 'Could not mark FAILED')
    return Response(
        {
            'success': True,
            'data': serialize_payout_recovery_row(updated),
            'message': 'Marked FAILED and released hold',
            'errors': [],
        }
    )
