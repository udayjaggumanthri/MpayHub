"""
Transaction and reporting views for the mPayhub platform.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils.dateparse import parse_date
from django.db.models import Sum
from decimal import Decimal

from apps.transactions.models import Transaction, PassbookEntry, CommissionLedger
from apps.wallets.models import Wallet, WalletTransaction
from apps.transactions.serializers import (
    TransactionSerializer,
    PassbookEntrySerializer,
    CommissionLedgerSerializer,
)
from apps.transactions.reporting_scope import (
    commission_ledger_q_for_team,
    get_report_scope,
    transaction_user_q,
)
from apps.transactions.report_filters import (
    apply_passbook_report_filters,
    apply_transaction_report_filters,
    apply_commission_ledger_filters,
)
from apps.transactions.report_operational import (
    platform_bbps_queryset,
    platform_payin_queryset,
    platform_payout_queryset,
    user_scope_payin_load_money_queryset,
)
from apps.transactions.report_api import (
    bbps_rows_for_transactions,
    bbps_rows_from_bill_payment,
    operational_status_financial_summary,
    passbook_period_header,
    passbook_rows,
    payin_rows_for_transactions,
    payin_rows_from_load_money,
    payout_rows_for_transactions,
    payout_rows_from_payout,
    stream_csv,
    txn_status_financial_summary,
)
from apps.core.permissions import IsAdmin
from apps.transactions.analytics_summary import get_gateway_analytics_summary
from apps.transactions.dashboard_stats import get_dashboard_transaction_status


def _audit_report_view(request, report_type: str, scope: str = ''):
    try:
        from apps.session_security.services.activity import record_report_viewed

        record_report_viewed(user=request.user, report_type=report_type, scope=scope or '')
    except Exception:  # noqa: BLE001
        pass


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transactions_list_view(request):
    """
    List transactions with filters.
    GET /api/transactions/
    Query: scope=self|team (team: downline-only activity for managers; Admin team = all users except own).
    """
    try:
        uq = transaction_user_q(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    transactions = Transaction.objects.filter(uq)
    
    # Apply filters
    transaction_type = request.query_params.get('type', 'all')
    if transaction_type != 'all':
        transactions = transactions.filter(transaction_type=transaction_type)
    
    status_filter = request.query_params.get('status')
    if status_filter:
        transactions = transactions.filter(status=status_filter)
    
    service_id = request.query_params.get('service_id')
    if service_id:
        transactions = transactions.filter(service_id__icontains=service_id)
    
    date_from = parse_date((request.query_params.get('date_from') or '').strip())
    if date_from:
        transactions = transactions.filter(created_at__date__gte=date_from)
    date_to = parse_date((request.query_params.get('date_to') or '').strip())
    if date_to:
        transactions = transactions.filter(created_at__date__lte=date_to)

    try:
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
    except Exception:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Invalid pagination parameters',
                'errors': {'page': ['Must be an integer >= 1'], 'page_size': ['Must be an integer between 1 and 500']},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if page < 1 or page_size < 1 or page_size > 500:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Invalid pagination parameters',
                'errors': {'page': ['Must be an integer >= 1'], 'page_size': ['Must be an integer between 1 and 500']},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    total = transactions.count()
    start = (page - 1) * page_size
    end = start + page_size

    paginated_transactions = transactions[start:end]
    serializer = TransactionSerializer(paginated_transactions, many=True)

    return Response(
        {
            'success': True,
            'data': {
                'transactions': serializer.data,
                'scope': get_report_scope(request),
                'total': total,
                'page': page,
                'page_size': page_size,
            },
            'message': 'Transactions retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_detail_view(request, transaction_id):
    """
    Get transaction details.
    GET /api/transactions/{id}/
    """
    try:
        transaction = Transaction.objects.get(id=transaction_id, user=request.user)
        serializer = TransactionSerializer(transaction)
        return Response({
            'success': True,
            'data': {'transaction': serializer.data},
            'message': 'Transaction retrieved successfully',
            'errors': []
        }, status=status.HTTP_200_OK)
    except Transaction.DoesNotExist:
        return Response({
            'success': False,
            'data': None,
            'message': 'Transaction not found',
            'errors': []
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def passbook_view(request):
    """
    Get passbook entries.
    GET /api/passbook/
    Query: scope=self|team — team merges passbooks for your downline (same rules as transaction reports).
    """
    try:
        uq = transaction_user_q(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    entries = PassbookEntry.objects.filter(uq).select_related('user', 'initiator_user')
    entries = apply_passbook_report_filters(entries, request)

    period_summary = passbook_period_header(entries)

    try:
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
    except Exception:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Invalid pagination parameters',
                'errors': {'page': ['Must be an integer >= 1'], 'page_size': ['Must be an integer between 1 and 500']},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if page < 1 or page_size < 1 or page_size > 500:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Invalid pagination parameters',
                'errors': {'page': ['Must be an integer >= 1'], 'page_size': ['Must be an integer between 1 and 500']},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    total = entries.count()
    start = (page - 1) * page_size
    end = start + page_size

    paginated_entries = list(entries.order_by('-created_at')[start:end])
    serializer = PassbookEntrySerializer(paginated_entries, many=True)
    enterprise_rows = passbook_rows(request, paginated_entries)

    return Response(
        {
            'success': True,
            'data': {
                'entries': serializer.data,
                'rows': enterprise_rows,
                'period_summary': period_summary,
                'scope': get_report_scope(request),
                'total': total,
                'page': page,
                'page_size': page_size,
            },
            'message': 'Passbook entries retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


def _report_page_params(request):
    try:
        page_size = int(request.query_params.get('page_size', 50))
    except ValueError:
        page_size = 50
    page_size = max(1, min(page_size, 500))
    try:
        page = int(request.query_params.get('page', 1))
    except ValueError:
        page = 1
    page = max(1, page)
    return page, page_size


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def dashboard_transaction_status_counts_view(request):
    """
    Platform-wide Pending/Success/Failed counts for admin dashboard.
    GET /api/reports/dashboard/transaction-status-counts/
    Query: module=all|payin|payout|bbps, interval=daily|monthly|yearly, date_from, date_to
    """
    module = (request.query_params.get('module') or 'all').strip().lower()
    interval = (request.query_params.get('interval') or 'daily').strip().lower()
    date_from = (request.query_params.get('date_from') or '').strip() or None
    date_to = (request.query_params.get('date_to') or '').strip() or None

    data = get_dashboard_transaction_status(
        module=module,
        interval=interval,
        date_from_raw=date_from,
        date_to_raw=date_to,
    )
    return Response(
        {
            'success': True,
            'data': data,
            'message': 'OK',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def analytics_summary_view(request):
    """
    Gateway-wise sales/profit analytics grouped by daily or monthly buckets.
    Admin-only; platform-wide SUCCESS pay-ins for all users (LoadMoney, not scope=self).
    GET /api/reports/analytics/summary/?interval=daily|monthly&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&gateway=...
    """
    interval = (request.query_params.get('interval') or 'daily').strip().lower()
    date_from = (request.query_params.get('date_from') or '').strip() or None
    date_to = (request.query_params.get('date_to') or '').strip() or None
    gateway_filter = (request.query_params.get('gateway') or '').strip()

    data = get_gateway_analytics_summary(
        interval=interval,
        date_from_raw=date_from,
        date_to_raw=date_to,
        gateway_filter=gateway_filter,
    )
    return Response(
        {
            'success': True,
            'data': data,
            'message': 'Analytics summary retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payin_report_view(request):
    """
    Pay In report (enterprise).
    GET /api/reports/payin/
    """
    try:
        scope = get_report_scope(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    page, page_size = _report_page_params(request)
    if scope == 'platform':
        qs = platform_payin_queryset(request)
        summary = operational_status_financial_summary(qs)
        total = qs.count()
        start = (page - 1) * page_size
        slice_qs = list(qs[start : start + page_size])
        rows = payin_rows_from_load_money(request, slice_qs)
        tx_data = []
    else:
        try:
            qs = user_scope_payin_load_money_queryset(request)
        except PermissionDenied as e:
            return Response(
                {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
                status=status.HTTP_403_FORBIDDEN,
            )
        summary = operational_status_financial_summary(qs)
        total = qs.count()
        start = (page - 1) * page_size
        slice_qs = list(qs[start : start + page_size])
        rows = payin_rows_from_load_money(request, slice_qs)
        tx_data = []
    _audit_report_view(request, 'payin', scope)
    return Response(
        {
            'success': True,
            'data': {
                'transactions': tx_data,
                'rows': rows,
                'scope': scope,
                'summary': summary,
                'total': total,
                'page': page,
                'page_size': page_size,
            },
            'message': 'Pay In report retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payout_report_view(request):
    """
    Pay Out report (enterprise).
    GET /api/reports/payout/
    """
    try:
        scope = get_report_scope(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    page, page_size = _report_page_params(request)
    if scope == 'platform':
        qs = platform_payout_queryset(request)
        summary = operational_status_financial_summary(qs)
        total = qs.count()
        start = (page - 1) * page_size
        slice_qs = list(qs[start : start + page_size])
        rows = payout_rows_from_payout(request, slice_qs)
        tx_data = []
    else:
        try:
            uq = transaction_user_q(request)
        except PermissionDenied as e:
            return Response(
                {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = (
            Transaction.objects.filter(uq, transaction_type='payout')
            .select_related('user', 'agent_user')
            .order_by('-created_at')
        )
        qs = apply_transaction_report_filters(qs, request, include_customer_mobile=False)
        summary = txn_status_financial_summary(qs)
        total = qs.count()
        start = (page - 1) * page_size
        slice_qs = list(qs[start : start + page_size])
        tx_data = TransactionSerializer(slice_qs, many=True).data
        rows = payout_rows_for_transactions(request, slice_qs)
    _audit_report_view(request, 'payout', scope)
    return Response(
        {
            'success': True,
            'data': {
                'transactions': tx_data,
                'rows': rows,
                'scope': scope,
                'summary': summary,
                'total': total,
                'page': page,
                'page_size': page_size,
            },
            'message': 'Pay Out report retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bbps_report_view(request):
    """
    BBPS report (enterprise).
    GET /api/reports/bbps/
    """
    try:
        scope = get_report_scope(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    page, page_size = _report_page_params(request)
    if scope == 'platform':
        qs = platform_bbps_queryset(request)
        summary = operational_status_financial_summary(qs)
        total = qs.count()
        start = (page - 1) * page_size
        slice_qs = list(qs[start : start + page_size])
        rows = bbps_rows_from_bill_payment(request, slice_qs, serial_offset=start)
        tx_data = []
    else:
        try:
            uq = transaction_user_q(request)
        except PermissionDenied as e:
            return Response(
                {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = (
            Transaction.objects.filter(uq, transaction_type='bbps')
            .select_related('user', 'agent_user')
            .order_by('-created_at')
        )
        qs = apply_transaction_report_filters(qs, request, include_customer_mobile=False)
        summary = txn_status_financial_summary(qs)
        total = qs.count()
        start = (page - 1) * page_size
        slice_qs = list(qs[start : start + page_size])
        tx_data = TransactionSerializer(slice_qs, many=True).data
        rows = bbps_rows_for_transactions(request, slice_qs, serial_offset=start)
    _audit_report_view(request, 'bbps', scope)
    return Response(
        {
            'success': True,
            'data': {
                'transactions': tx_data,
                'rows': rows,
                'scope': scope,
                'summary': summary,
                'total': total,
                'page': page,
                'page_size': page_size,
            },
            'message': 'BBPS report retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def commission_report_view(request):
    """
    Commission report.
    GET /api/reports/commission/
    """
    try:
        ledger_extra = commission_ledger_q_for_team(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )

    ledger_qs = (
        CommissionLedger.objects.filter(user=request.user)
        .filter(ledger_extra)
        .order_by('-created_at')
    )
    ledger_qs = apply_commission_ledger_filters(ledger_qs, request)
    ledger_total = ledger_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    page, page_size = _report_page_params(request)
    ledger_count = ledger_qs.count()

    try:
        commission_wallet = Wallet.objects.get(user=request.user, wallet_type='commission')
        transactions = WalletTransaction.objects.filter(
            wallet=commission_wallet,
            transaction_type='credit',
        ).order_by('-created_at')
        date_from = parse_date((request.query_params.get('date_from') or '').strip())
        date_to = parse_date((request.query_params.get('date_to') or '').strip())
        if date_from:
            transactions = transactions.filter(created_at__date__gte=date_from)
        if date_to:
            transactions = transactions.filter(created_at__date__lte=date_to)
        if get_report_scope(request) == 'team':
            transactions = transactions.none()
            total_commission = ledger_total
        else:
            total_commission = transactions.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        current_balance = commission_wallet.balance

        from apps.wallets.serializers import WalletTransactionSerializer

        start = (page - 1) * page_size
        end = start + page_size
        if ledger_count > 0:
            total = ledger_count
            ledger_slice = list(ledger_qs[start:end])
            txn_slice = []
        else:
            txn_qs = transactions
            total = txn_qs.count()
            ledger_slice = []
            txn_slice = list(txn_qs[start:end])

        ledger_ser = CommissionLedgerSerializer(ledger_slice, many=True)
        serializer = WalletTransactionSerializer(txn_slice, many=True)

        _audit_report_view(request, 'commission', get_report_scope(request))
        return Response(
            {
                'success': True,
                'data': {
                    'transactions': serializer.data,
                    'ledger': ledger_ser.data,
                    'scope': get_report_scope(request),
                    'total': total,
                    'page': page,
                    'page_size': page_size,
                    'summary': {
                        'total_commission': str(total_commission),
                        'ledger_total': str(ledger_total),
                        'current_balance': str(current_balance),
                        'count': transactions.count(),
                        'ledger_count': ledger_count,
                    },
                },
                'message': 'Commission report retrieved successfully',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )
    except Wallet.DoesNotExist:
        start = (page - 1) * page_size
        end = start + page_size
        ledger_slice = list(ledger_qs[start:end])
        ledger_ser = CommissionLedgerSerializer(ledger_slice, many=True)
        return Response(
            {
                'success': True,
                'data': {
                    'transactions': [],
                    'ledger': ledger_ser.data,
                    'scope': get_report_scope(request),
                    'total': ledger_count,
                    'page': page,
                    'page_size': page_size,
                    'summary': {
                        'total_commission': '0.0000',
                        'ledger_total': str(ledger_total),
                        'current_balance': '0.0000',
                        'count': 0,
                        'ledger_count': ledger_count,
                    },
                },
                'message': 'Commission report retrieved successfully',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )


def _payin_report_queryset(request):
    if get_report_scope(request) == 'platform':
        return platform_payin_queryset(request)
    return user_scope_payin_load_money_queryset(request)


def _payout_report_queryset(request):
    if get_report_scope(request) == 'platform':
        return platform_payout_queryset(request)
    uq = transaction_user_q(request)
    qs = Transaction.objects.filter(uq, transaction_type='payout').select_related('user', 'agent_user').order_by(
        '-created_at'
    )
    return apply_transaction_report_filters(qs, request, include_customer_mobile=False)


def _bbps_report_queryset(request):
    if get_report_scope(request) == 'platform':
        return platform_bbps_queryset(request)
    uq = transaction_user_q(request)
    qs = Transaction.objects.filter(uq, transaction_type='bbps').select_related('user', 'agent_user').order_by(
        '-created_at'
    )
    return apply_transaction_report_filters(qs, request, include_customer_mobile=False)


def _passbook_report_queryset(request):
    uq = transaction_user_q(request)
    qs = PassbookEntry.objects.filter(uq).select_related('user', 'initiator_user').order_by('-created_at')
    return apply_passbook_report_filters(qs, request)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payin_report_export_csv(request):
    try:
        qs = _payin_report_queryset(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    scope = get_report_scope(request)
    slice_list = list(qs[:5000])
    if scope == 'platform':
        rows = payin_rows_from_load_money(request, slice_list)
    else:
        rows = payin_rows_for_transactions(request, slice_list)
    headers = [
        'created_at',
        'service_id',
        'service_name',
        'customer_id',
        'mode',
        'principal',
        'service_charge',
        'net_credit',
        'opening_balance',
        'closing_balance',
        'status',
        'agent_code',
        'agent_name',
        'agent_role',
        'agent_mobile',
    ]
    csv_rows = [
        [
            r['created_at'],
            r['service_id'],
            r['service_name'],
            r['customer_id'],
            r['mode'],
            r['principal'],
            r['service_charge'],
            r['net_credit'],
            r['opening_balance'],
            r['closing_balance'],
            r['status'],
            r['agent_details']['user_code'],
            r['agent_details']['name'],
            r['agent_details']['role'],
            r['agent_details']['mobile'],
        ]
        for r in rows
    ]
    return stream_csv('payin_report', headers, csv_rows)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payout_report_export_csv(request):
    try:
        qs = _payout_report_queryset(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    scope = get_report_scope(request)
    slice_list = list(qs[:5000])
    if scope == 'platform':
        rows = payout_rows_from_payout(request, slice_list)
    else:
        rows = payout_rows_for_transactions(request, slice_list)
    headers = [
        'created_at',
        'transaction_id',
        'bank_name',
        'account_masked',
        'transfer_amount',
        'payout_charge',
        'platform_fee',
        'net_debit',
        'opening_balance',
        'closing_balance',
        'status',
        'agent_code',
        'agent_name',
        'agent_role',
        'agent_mobile',
    ]
    csv_rows = [
        [
            r['created_at'],
            r['transaction_id'],
            r['bank_name'],
            r['account_number_masked'],
            r['transfer_amount'],
            r['payout_charge'],
            r['platform_fee'],
            r['net_debit'],
            r['opening_balance'],
            r['closing_balance'],
            r['status'],
            r['agent_details']['user_code'],
            r['agent_details']['name'],
            r['agent_details']['role'],
            r['agent_details']['mobile'],
        ]
        for r in rows
    ]
    return stream_csv('payout_report', headers, csv_rows)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bbps_report_export_csv(request):
    try:
        qs = _bbps_report_queryset(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    scope = get_report_scope(request)
    slice_list = list(qs[:5000])
    if scope == 'platform':
        rows = bbps_rows_from_bill_payment(request, slice_list)
    else:
        rows = bbps_rows_for_transactions(request, slice_list)
    headers = [
        'serial',
        'created_at',
        'transaction_id',
        'request_id',
        'category',
        'biller',
        'bill_amount',
        'platform_fee',
        'opening_balance',
        'closing_balance',
        'status',
        'status_token',
        'agent_code',
        'agent_name',
        'agent_role',
        'agent_mobile',
    ]
    csv_rows = [
        [
            r['serial'],
            r['created_at'],
            r['transaction_id'],
            r['request_id'],
            r['category'],
            r['biller'],
            r['bill_amount'],
            r['platform_fee'],
            r['opening_balance'],
            r['closing_balance'],
            r['status'],
            r['status_token'],
            r['agent_details']['user_code'],
            r['agent_details']['name'],
            r['agent_details']['role'],
            r['agent_details']['mobile'],
        ]
        for r in rows
    ]
    return stream_csv('bbps_report', headers, csv_rows)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def passbook_report_export_csv(request):
    try:
        qs = _passbook_report_queryset(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    rows = passbook_rows(request, list(qs[:5000]))
    headers = [
        'created_at',
        'service_type',
        'service_id',
        'service_name',
        'description',
        'debit',
        'credit',
        'opening_balance',
        'closing_balance',
        'wallet_type',
        'owner_user_code',
        'agent_code',
        'agent_name',
        'agent_role',
        'agent_mobile',
    ]
    csv_rows = [
        [
            r['created_at'],
            r['service_type'],
            r['service_id'],
            r['service_name'],
            r['description'],
            r['debit'],
            r['credit'],
            r['opening_balance'],
            r['closing_balance'],
            r['wallet_type'],
            r['owner_user_code'],
            r['agent_details']['user_code'],
            r['agent_details']['name'],
            r['agent_details']['role'],
            r['agent_details']['mobile'],
        ]
        for r in rows
    ]
    return stream_csv('passbook_report', headers, csv_rows)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def commission_report_export_csv(request):
    try:
        ledger_extra = commission_ledger_q_for_team(request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    ledger_qs = (
        CommissionLedger.objects.filter(user=request.user)
        .filter(ledger_extra)
        .order_by('-created_at')
    )
    ledger_qs = apply_commission_ledger_filters(ledger_qs, request)
    rows = list(ledger_qs[:5000])
    headers = [
        'created_at',
        'reference_service_id',
        'source',
        'wallet_type',
        'amount',
        'source_user_code',
        'source_name_snapshot',
        'source_role',
        'slice',
        'role_at_time',
    ]
    csv_rows = [
        [
            r.created_at.isoformat() if r.created_at else '',
            r.reference_service_id,
            r.source,
            r.wallet_type,
            str(r.amount),
            r.source_user_code,
            r.source_name_snapshot,
            r.source_role,
            (r.meta or {}).get('slice', ''),
            r.role_at_time,
        ]
        for r in rows
    ]
    return stream_csv('commission_report', headers, csv_rows)
