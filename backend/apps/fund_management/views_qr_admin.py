"""Admin views for QR account master and QR pay-in operations."""
import csv
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q, Sum
from django.http import Http404, StreamingHttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import IsAdmin
from apps.fund_management.models import LoadMoney, PayInQrAccount, PayInQrApprovalAudit
from apps.fund_management.money_utils import money_q
from apps.fund_management.qr_approval import (
    REJECT_REASON_CODES,
    approve_qr_payin,
    reject_qr_payin,
    release_qr_utr,
)
from apps.fund_management.qr_limits import qr_limit_context, qr_usage_map_24h
from apps.fund_management.serializers_qr import (
    PayInQrAccountSerializer,
    PayInQrApprovalAuditSerializer,
    QrPayInApproveSerializer,
    QrPayInOperationDetailSerializer,
    QrPayInOperationListSerializer,
    QrPayInRejectSerializer,
    QrPayInReleaseUtrSerializer,
)
from apps.fund_management.payin_distribution import (
    _compute_payin_distribution,
    serialize_payin_distribution_for_api,
)
from apps.fund_management.qr_image import qr_image_file_response

logger = logging.getLogger(__name__)


def _serializer_error_message(errors) -> str:
    if not errors:
        return 'Invalid input'
    for field, msgs in errors.items():
        if isinstance(msgs, (list, tuple)) and msgs:
            return f'{field}: {msgs[0]}'
        if isinstance(msgs, str):
            return f'{field}: {msgs}'
    return 'Invalid input'


def _qr_operations_queryset(request):
    qs = (
        LoadMoney.objects.filter(collection_rail='qr', is_deleted=False)
        .select_related('user', 'package', 'pay_in_qr_account', 'reviewed_by')
        .order_by('-created_at')
    )
    status_filter = (request.query_params.get('status') or '').strip().upper()
    if status_filter:
        qs = qs.filter(status=status_filter)
    rail = (request.query_params.get('rail') or '').strip().lower()
    if rail and rail != 'qr':
        qs = qs.none()
    qr_id = request.query_params.get('qr_account_id')
    if qr_id and str(qr_id).isdigit():
        qs = qs.filter(pay_in_qr_account_id=int(qr_id))
    utr = (request.query_params.get('utr') or '').strip()
    if utr:
        qs = qs.filter(utr__icontains=utr)
    q = (request.query_params.get('q') or request.query_params.get('search') or '').strip()
    if q:
        qs = qs.filter(
            Q(transaction_id__icontains=q)
            | Q(utr__icontains=q)
            | Q(customer_name__icontains=q)
            | Q(customer_phone__icontains=q)
            | Q(user__email__icontains=q)
            | Q(user__member_id__icontains=q)
        )
    role = (request.query_params.get('role') or '').strip()
    if role:
        qs = qs.filter(user__role=role)
    date_from = parse_date((request.query_params.get('date_from') or '').strip())
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    date_to = parse_date((request.query_params.get('date_to') or '').strip())
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    amount_min = request.query_params.get('amount_min')
    if amount_min:
        try:
            qs = qs.filter(submitted_amount__gte=Decimal(str(amount_min)))
        except (InvalidOperation, ValueError):
            pass
    amount_max = request.query_params.get('amount_max')
    if amount_max:
        try:
            qs = qs.filter(submitted_amount__lte=Decimal(str(amount_max)))
        except (InvalidOperation, ValueError):
            pass
    return qs


class PayInQrAccountViewSet(viewsets.ModelViewSet):
    queryset = PayInQrAccount.objects.filter(is_deleted=False).order_by('sort_order', 'display_name')
    serializer_class = PayInQrAccountSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = super().get_queryset()
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(display_name__icontains=search)
                | Q(account_display_name__icontains=search)
                | Q(upi_vpa__icontains=search)
            )
        st = (self.request.query_params.get('status') or '').strip()
        if st:
            qs = qs.filter(status=st)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        except (TypeError, ValueError):
            page, page_size = 1, 20
        total = qs.count()
        start = (page - 1) * page_size
        items = qs[start : start + page_size]
        qr_ids = [q.pk for q in items]
        usage = qr_usage_map_24h(qr_ids)
        ser = self.get_serializer(items, many=True)
        rows = []
        for row, item in zip(ser.data, items):
            ctx = qr_limit_context(item, used=usage.get(item.pk))
            row['daily_used'] = ctx['daily_used']
            row['remaining_daily_limit'] = ctx['remaining_daily_limit']
            rows.append(row)
        return Response(
            {
                'success': True,
                'data': {'results': rows, 'total': total, 'page': page, 'page_size': page_size},
                'message': 'OK',
                'errors': [],
            }
        )

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': _serializer_error_message(ser.errors),
                    'errors': ser.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj = ser.save()
        return Response(
            {
                'success': True,
                'data': {'qr_account': self.get_serializer(obj).data},
                'message': 'QR account created',
                'errors': [],
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        ser = self.get_serializer(instance, data=request.data, partial=partial)
        if not ser.is_valid():
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': _serializer_error_message(ser.errors),
                    'errors': ser.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj = ser.save()
        return Response(
            {
                'success': True,
                'data': {'qr_account': self.get_serializer(obj).data},
                'message': 'QR account updated',
                'errors': [],
            }
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        return Response({'success': True, 'data': None, 'message': 'QR account removed', 'errors': []})

    @action(detail=True, methods=['get'], url_path='qr-image')
    def qr_image(self, request, pk=None):
        account = self.get_object()
        if not account.qr_image:
            raise Http404
        return qr_image_file_response(account.qr_image, download_name=f'qr-{account.pk}.png')

    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        qr = self.get_object()
        qr.status = 'inactive' if qr.status == 'active' else 'active'
        qr.save(update_fields=['status', 'updated_at'])
        return Response(
            {
                'success': True,
                'data': {'qr_account': self.get_serializer(qr).data},
                'message': 'Status updated',
                'errors': [],
            }
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def qr_operations_stats_view(request):
    today = timezone.localdate()
    base = LoadMoney.objects.filter(collection_rail='qr', is_deleted=False)
    pending = base.filter(status='PENDING_REVIEW').count()
    approved_today = base.filter(status='SUCCESS', reviewed_at__date=today).count()
    rejected_today = base.filter(status='FAILED', reviewed_at__date=today).count()
    volume_today = (
        base.filter(status='SUCCESS', reviewed_at__date=today).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    )
    qr_stats = []
    for qr in PayInQrAccount.objects.filter(is_deleted=False, status='active').order_by('sort_order')[:50]:
        ctx = qr_limit_context(qr)
        qr_stats.append(
            {
                'id': qr.id,
                'name': qr.display_name,
                'daily_limit': ctx['daily_limit'],
                'daily_used': ctx['daily_used'],
                'remaining_daily_limit': ctx['remaining_daily_limit'],
                'utilization_pct': (
                    float(Decimal(ctx['daily_used']) / Decimal(ctx['daily_limit']) * 100)
                    if Decimal(ctx['daily_limit']) > 0
                    else 0.0
                ),
            }
        )
    return Response(
        {
            'success': True,
            'data': {
                'pending_count': pending,
                'approved_today': approved_today,
                'rejected_today': rejected_today,
                'volume_today': str(money_q(volume_today)),
                'qr_accounts': qr_stats,
            },
            'message': 'OK',
            'errors': [],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def qr_operations_list_view(request):
    qs = _qr_operations_queryset(request)
    try:
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))
    except (TypeError, ValueError):
        page, page_size = 1, 20
    total = qs.count()
    start = (page - 1) * page_size
    items = list(qs[start : start + page_size])
    ser = QrPayInOperationListSerializer(items, many=True, context={'request': request})
    return Response(
        {
            'success': True,
            'data': {'results': ser.data, 'total': total, 'page': page, 'page_size': page_size},
            'message': 'OK',
            'errors': [],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def qr_operations_detail_view(request, pk: int):
    lm = (
        LoadMoney.objects.filter(pk=pk, collection_rail='qr', is_deleted=False)
        .select_related('user', 'package', 'pay_in_qr_account', 'reviewed_by')
        .prefetch_related('qr_approval_audits__actor')
        .first()
    )
    if not lm:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    preview = None
    if lm.package and lm.status == 'PENDING_REVIEW':
        amt = lm.submitted_amount or lm.amount
        try:
            from apps.fund_management.rail_fees import resolve_rail_gateway_fee_pct

            rail_fee = resolve_rail_gateway_fee_pct(
                lm.package, qr_account_id=lm.pay_in_qr_account_id
            )
            preview = serialize_payin_distribution_for_api(
                _compute_payin_distribution(lm.package, amt, lm.user, gateway_fee_pct=rail_fee)
            )
        except Exception:
            preview = None
    ser = QrPayInOperationDetailSerializer(lm, context={'request': request})
    data = ser.data
    data['approval_preview'] = preview
    data['audits'] = PayInQrApprovalAuditSerializer(
        lm.qr_approval_audits.all(), many=True
    ).data
    return Response({'success': True, 'data': data, 'message': 'OK', 'errors': []})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def qr_operations_approve_view(request, pk: int):
    lm = LoadMoney.objects.filter(pk=pk, collection_rail='qr', is_deleted=False).first()
    if not lm:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    ser = QrPayInApproveSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        updated = approve_qr_payin(
            load_money=lm,
            actor=request.user,
            approved_amount=ser.validated_data['approved_amount'],
            internal_note=ser.validated_data.get('internal_note') or '',
        )
    except Exception as exc:
        from rest_framework.exceptions import ValidationError

        if isinstance(exc, ValidationError):
            return Response(
                {'success': False, 'data': None, 'message': str(exc.detail), 'errors': exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raise
    from apps.fund_management.serializers import LoadMoneySerializer

    return Response(
        {
            'success': True,
            'data': {'load_money': LoadMoneySerializer(updated, context={'request': request}).data},
            'message': 'Approved and wallet credited',
            'errors': [],
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def qr_operations_reject_view(request, pk: int):
    lm = LoadMoney.objects.filter(pk=pk, collection_rail='qr', is_deleted=False).first()
    if not lm:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    ser = QrPayInRejectSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        updated = reject_qr_payin(
            load_money=lm,
            actor=request.user,
            reason_code=ser.validated_data['reason_code'],
            reason_text=ser.validated_data.get('reason_text') or '',
            internal_note=ser.validated_data.get('internal_note') or '',
        )
    except Exception as exc:
        from rest_framework.exceptions import ValidationError

        if isinstance(exc, ValidationError):
            return Response(
                {'success': False, 'data': None, 'message': str(exc.detail), 'errors': exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raise
    from apps.fund_management.serializers import LoadMoneySerializer

    return Response(
        {
            'success': True,
            'data': {'load_money': LoadMoneySerializer(updated, context={'request': request}).data},
            'message': 'Rejected',
            'errors': [],
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def qr_operations_release_utr_view(request, pk: int):
    lm = LoadMoney.objects.filter(pk=pk, collection_rail='qr', is_deleted=False).first()
    if not lm:
        return Response(
            {'success': False, 'data': None, 'message': 'Not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    ser = QrPayInReleaseUtrSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        updated = release_qr_utr(
            load_money=lm,
            actor=request.user,
            internal_note=ser.validated_data['internal_note'],
        )
    except Exception as exc:
        from rest_framework.exceptions import ValidationError

        if isinstance(exc, ValidationError):
            return Response(
                {'success': False, 'data': None, 'message': str(exc.detail), 'errors': exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raise
    from apps.fund_management.serializers import LoadMoneySerializer

    return Response(
        {
            'success': True,
            'data': {'load_money': LoadMoneySerializer(updated, context={'request': request}).data},
            'message': 'UTR released for reuse',
            'errors': [],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def qr_operations_export_csv_view(request):
    qs = _qr_operations_queryset(request)[:5000]
    headers = [
        'transaction_id',
        'created_at',
        'status',
        'user',
        'role',
        'qr_account',
        'submitted_amount',
        'approved_amount',
        'utr',
        'payment_date',
        'failure_reason',
    ]

    def row_iter():
        yield headers
        for lm in qs.iterator(chunk_size=200):
            yield [
                lm.transaction_id,
                lm.created_at.isoformat() if lm.created_at else '',
                lm.status,
                getattr(lm.user, 'email', ''),
                getattr(lm.user, 'role', ''),
                lm.pay_in_qr_account.display_name if lm.pay_in_qr_account else '',
                str(lm.submitted_amount or ''),
                str(lm.amount or ''),
                lm.utr or '',
                str(lm.payment_date or ''),
                (lm.failure_reason or '')[:500],
            ]

    class Echo:
        def write(self, value):
            return value

    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    response = StreamingHttpResponse(
        (writer.writerow(r) for r in row_iter()),
        content_type='text/csv',
    )
    response['Content-Disposition'] = 'attachment; filename="qr_payin_operations.csv"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def qr_operations_export_xlsx_view(request):
    from apps.fund_management.qr_operations_export import build_qr_operations_xlsx

    qs = _qr_operations_queryset(request)[:5000]
    return build_qr_operations_xlsx(qs)
