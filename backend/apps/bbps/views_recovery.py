"""Admin BBPS recovery APIs — stuck payments, status sync, mark success/failed, complaint."""
from __future__ import annotations

from django.db.models import Min, Q, Sum

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.bbps.models import BbpsPaymentAttempt
from apps.bbps.service_flow.complaint_service import register_complaint
from apps.bbps.service_flow.recovery import (
    admin_mark_bbps_failed,
    admin_mark_bbps_success,
    serialize_bbps_recovery_row,
    stuck_recovery_queryset,
)
from apps.bbps.service_flow.status_service import poll_attempt_status
from apps.core.exceptions import TransactionFailed
from apps.core.permissions import IsAdmin


def _page(request):
    try:
        page_size = int(request.query_params.get('page_size') or 20)
    except (TypeError, ValueError):
        page_size = 20
    page_size = max(1, min(page_size, 100))
    try:
        page = int(request.query_params.get('page') or 1)
    except (TypeError, ValueError):
        page = 1
    return max(1, page), page_size


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def bbps_recovery_stats_view(request):
    qs = stuck_recovery_queryset()
    agg = qs.aggregate(held=Sum('wallet_hold_amount'), oldest=Min('created_at'))
    oldest = agg.get('oldest')
    return Response(
        {
            'success': True,
            'data': {
                'stuck': qs.count(),
                'held_amount': str(agg.get('held') or 0),
                'oldest_created_at': oldest.isoformat() if oldest else None,
            },
            'message': 'OK',
            'errors': [],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def bbps_recovery_list_view(request):
    q = (request.query_params.get('q') or '').strip()
    page, page_size = _page(request)
    qs = stuck_recovery_queryset()
    if q:
        qs = qs.filter(
            Q(service_id__icontains=q)
            | Q(request_id__icontains=q)
            | Q(txn_ref_id__icontains=q)
            | Q(user__phone__icontains=q)
            | Q(user__user_id__icontains=q)
            | Q(bill_payment__service_id__icontains=q)
            | Q(bill_payment__request_id__icontains=q)
        )
    total = qs.count()
    start = (page - 1) * page_size
    rows = [serialize_bbps_recovery_row(row) for row in qs[start : start + page_size]]
    return Response(
        {
            'success': True,
            'data': {'results': rows, 'total': total, 'page': page, 'page_size': page_size},
            'message': 'OK',
            'errors': [],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def bbps_recovery_detail_view(request, pk: int):
    attempt = stuck_recovery_queryset().filter(pk=pk).first() or (
        BbpsPaymentAttempt.objects.filter(pk=pk, is_deleted=False).select_related('bill_payment', 'user').first()
    )
    if not attempt:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(
        {'success': True, 'data': serialize_bbps_recovery_row(attempt), 'message': 'OK', 'errors': []}
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def bbps_recovery_check_status_view(request, pk: int):
    attempt = BbpsPaymentAttempt.objects.filter(pk=pk, is_deleted=False).select_related('bill_payment', 'user').first()
    if not attempt:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    result = poll_attempt_status(attempt, requested_by=request.user, source='admin')
    result.attempt.refresh_from_db()
    return Response(
        {
            'success': True,
            'data': {
                'payment': serialize_bbps_recovery_row(result.attempt),
                'status_changed': result.status_changed,
                'cooling_active': result.cooling_active,
                'retry_after_seconds': result.retry_after_seconds,
            },
            'message': result.message,
            'errors': [],
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def bbps_recovery_mark_success_view(request, pk: int):
    attempt = BbpsPaymentAttempt.objects.filter(pk=pk, is_deleted=False).first()
    if not attempt:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    updated = admin_mark_bbps_success(
        attempt=attempt,
        actor=request.user,
        internal_note=str(request.data.get('internal_note') or ''),
    )
    return Response(
        {
            'success': True,
            'data': serialize_bbps_recovery_row(updated),
            'message': 'Marked success',
            'errors': [],
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def bbps_recovery_mark_failed_view(request, pk: int):
    attempt = BbpsPaymentAttempt.objects.filter(pk=pk, is_deleted=False).first()
    if not attempt:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    updated = admin_mark_bbps_failed(
        attempt=attempt,
        actor=request.user,
        reason=str(request.data.get('reason') or ''),
        internal_note=str(request.data.get('internal_note') or ''),
    )
    return Response(
        {
            'success': True,
            'data': serialize_bbps_recovery_row(updated),
            'message': 'Marked failed',
            'errors': [],
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def bbps_recovery_complaint_view(request, pk: int):
    """Raise a complaint for any retailer's payment. The complaint stays on that retailer."""
    attempt = (
        BbpsPaymentAttempt.objects.filter(pk=pk, is_deleted=False)
        .select_related('user', 'bill_payment')
        .first()
    )
    if not attempt or not attempt.user_id:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    txn = str(attempt.txn_ref_id or request.data.get('txn_ref_id') or '').strip()
    try:
        row = register_complaint(
            user=attempt.user,
            txn_ref_id=txn,
            complaint_desc=str(request.data.get('complaint_desc') or ''),
            complaint_disposition=str(request.data.get('complaint_disposition') or ''),
        )
    except TransactionFailed as exc:
        return Response(
            {'success': False, 'data': None, 'message': str(exc), 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {
            'success': True,
            'data': {
                'complaint_id': row.complaint_id,
                'user_id': attempt.user_id,
                'txn_ref_id': row.txn_ref_id,
            },
            'message': 'Complaint registered for the retailer',
            'errors': [],
        }
    )
