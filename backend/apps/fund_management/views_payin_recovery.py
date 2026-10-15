"""Admin pay-in recovery APIs."""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import IsAdmin
from apps.fund_management.models import LoadMoney
from apps.fund_management.payin_recovery import (
    admin_adjust_payin_fee,
    admin_mark_payin_failed,
    admin_mark_payin_success,
    payin_recovery_queryset,
    payin_recovery_stats,
    serialize_payin_recovery_row,
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


def _load(pk):
    return (
        LoadMoney.objects.filter(pk=pk, is_deleted=False)
        .select_related('user', 'user__profile', 'package', 'payment_gateway', 'pay_in_qr_account')
        .first()
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def payin_recovery_stats_view(request):
    return Response({'success': True, 'data': payin_recovery_stats(), 'message': 'OK', 'errors': []})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def payin_recovery_list_view(request):
    q = (request.query_params.get('q') or '').strip()
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
    rows = list(payin_recovery_queryset(q))
    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start:start + page_size]
    return Response(
        {
            'success': True,
            'data': {
                'results': [serialize_payin_recovery_row(row) for row in page_rows],
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
def payin_recovery_detail_view(request, pk: int):
    lm = _load(pk)
    if not lm:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response({'success': True, 'data': serialize_payin_recovery_row(lm), 'message': 'OK', 'errors': []})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def payin_recovery_mark_success_view(request, pk: int):
    lm = _load(pk)
    if not lm:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        updated = admin_mark_payin_success(
            load_money=lm,
            actor=request.user,
            utr=str(request.data.get('utr') or ''),
            internal_note=str(request.data.get('internal_note') or ''),
        )
    except ValidationError as exc:
        return _err(exc, 'Could not mark success')
    updated = _load(updated.pk) or updated
    return Response(
        {
            'success': True,
            'data': serialize_payin_recovery_row(updated),
            'message': 'Pay-in marked successful',
            'errors': [],
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def payin_recovery_mark_failed_view(request, pk: int):
    lm = _load(pk)
    if not lm:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        updated = admin_mark_payin_failed(
            load_money=lm,
            actor=request.user,
            reason=str(request.data.get('reason') or ''),
            internal_note=str(request.data.get('internal_note') or ''),
        )
    except ValidationError as exc:
        return _err(exc, 'Could not mark failed')
    updated = _load(updated.pk) or updated
    return Response(
        {
            'success': True,
            'data': serialize_payin_recovery_row(updated),
            'message': 'Pay-in marked failed',
            'errors': [],
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def payin_recovery_adjust_view(request, pk: int):
    lm = _load(pk)
    if not lm:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        updated = admin_adjust_payin_fee(
            load_money=lm,
            actor=request.user,
            target=str(request.data.get('target') or ''),
        )
    except ValidationError as exc:
        return _err(exc, 'Could not adjust this pay-in')
    updated = _load(updated.pk) or updated
    return Response(
        {
            'success': True,
            'data': serialize_payin_recovery_row(updated),
            'message': 'Wallet adjusted for this pay-in',
            'errors': [],
        }
    )
