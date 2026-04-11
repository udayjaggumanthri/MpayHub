"""
Transaction and reporting views for the mPayhub platform.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db import models
from datetime import timedelta
from apps.transactions.models import Transaction, PassbookEntry
from apps.wallets.models import Wallet, WalletTransaction
from apps.transactions.serializers import TransactionSerializer, PassbookEntrySerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transactions_list_view(request):
    """
    List transactions with filters.
    GET /api/transactions/
    """
    transactions = Transaction.objects.filter(user=request.user)
    
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
    except ValueError:
        page_size = 20
    page_size = max(1, min(page_size, 500))

    try:
        page = int(request.query_params.get('page', 1))
    except ValueError:
        page = 1
    page = max(1, page)

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
    """
    entries = PassbookEntry.objects.filter(user=request.user)
    
    # Apply filters
    date_from = parse_date((request.query_params.get('date_from') or '').strip())
    if date_from:
        entries = entries.filter(created_at__date__gte=date_from)
    date_to = parse_date((request.query_params.get('date_to') or '').strip())
    if date_to:
        entries = entries.filter(created_at__date__lte=date_to)

    search = request.query_params.get('search')
    if search:
        entries = entries.filter(
            models.Q(service_id__icontains=search) | models.Q(description__icontains=search)
        )

    wallet_type = request.query_params.get('wallet_type')
    if wallet_type in ('main', 'commission', 'bbps'):
        entries = entries.filter(wallet_type=wallet_type)

    try:
        page_size = int(request.query_params.get('page_size', 20))
    except ValueError:
        page_size = 20
    page_size = max(1, min(page_size, 500))

    try:
        page = int(request.query_params.get('page', 1))
    except ValueError:
        page = 1
    page = max(1, page)

    total = entries.count()
    start = (page - 1) * page_size
    end = start + page_size

    paginated_entries = entries[start:end]
    serializer = PassbookEntrySerializer(paginated_entries, many=True)

    return Response(
        {
            'success': True,
            'data': {
                'entries': serializer.data,
                'total': total,
                'page': page,
                'page_size': page_size,
            },
            'message': 'Passbook entries retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payin_report_view(request):
    """
    Pay In report.
    GET /api/reports/payin/
    """
    transactions = Transaction.objects.filter(
        user=request.user,
        transaction_type='payin',
        status='SUCCESS'
    )
    
    # Apply date filters
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if date_from and date_to:
        transactions = transactions.filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to
        )
    
    total_amount = sum(t.amount for t in transactions)
    total_charge = sum(t.charge for t in transactions)
    total_net = sum(t.net_amount or t.amount for t in transactions)
    
    serializer = TransactionSerializer(transactions, many=True)
    
    return Response({
        'success': True,
        'data': {
            'transactions': serializer.data,
            'summary': {
                'total_amount': float(total_amount),
                'total_charge': float(total_charge),
                'total_net': float(total_net),
                'count': transactions.count()
            }
        },
        'message': 'Pay In report retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payout_report_view(request):
    """
    Pay Out report.
    GET /api/reports/payout/
    """
    transactions = Transaction.objects.filter(
        user=request.user,
        transaction_type='payout',
        status='SUCCESS'
    )
    
    # Apply date filters
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if date_from and date_to:
        transactions = transactions.filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to
        )
    
    total_amount = sum(t.amount for t in transactions)
    total_charge = sum(t.charge for t in transactions)
    total_fee = sum(t.platform_fee or 0 for t in transactions)
    
    serializer = TransactionSerializer(transactions, many=True)
    
    return Response({
        'success': True,
        'data': {
            'transactions': serializer.data,
            'summary': {
                'total_amount': float(total_amount),
                'total_charge': float(total_charge),
                'total_fee': float(total_fee),
                'count': transactions.count()
            }
        },
        'message': 'Pay Out report retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bbps_report_view(request):
    """
    BBPS report.
    GET /api/reports/bbps/
    """
    transactions = Transaction.objects.filter(
        user=request.user,
        transaction_type='bbps',
        status='SUCCESS'
    )
    
    # Apply date filters
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if date_from and date_to:
        transactions = transactions.filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to
        )
    
    total_amount = sum(t.amount for t in transactions)
    total_charge = sum(t.charge for t in transactions)
    
    serializer = TransactionSerializer(transactions, many=True)
    
    return Response({
        'success': True,
        'data': {
            'transactions': serializer.data,
            'summary': {
                'total_amount': float(total_amount),
                'total_charge': float(total_charge),
                'count': transactions.count()
            }
        },
        'message': 'BBPS report retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def commission_report_view(request):
    """
    Commission report.
    GET /api/reports/commission/
    """
    # Get commission wallet transactions
    try:
        commission_wallet = Wallet.objects.get(user=request.user, wallet_type='commission')
        transactions = WalletTransaction.objects.filter(
            wallet=commission_wallet,
            transaction_type='credit'
        ).order_by('-created_at')
        
        # Apply date filters
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from and date_to:
            transactions = transactions.filter(
                created_at__date__gte=date_from,
                created_at__date__lte=date_to
            )
        
        total_commission = sum(t.amount for t in transactions)
        current_balance = commission_wallet.balance
        
        from apps.wallets.serializers import WalletTransactionSerializer
        serializer = WalletTransactionSerializer(transactions, many=True)
        
        return Response({
            'success': True,
            'data': {
                'transactions': serializer.data,
                'summary': {
                    'total_commission': float(total_commission),
                    'current_balance': float(current_balance),
                    'count': transactions.count()
                }
            },
            'message': 'Commission report retrieved successfully',
            'errors': []
        }, status=status.HTTP_200_OK)
    except Wallet.DoesNotExist:
        return Response({
            'success': True,
            'data': {
                'transactions': [],
                'summary': {
                    'total_commission': 0.0,
                    'current_balance': 0.0,
                    'count': 0
                }
            },
            'message': 'Commission report retrieved successfully',
            'errors': []
        }, status=status.HTTP_200_OK)
