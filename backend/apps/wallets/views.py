"""
Wallet views for the mPayhub platform.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.wallets.models import Wallet, WalletTransaction
from apps.transactions.models import PassbookEntry
from apps.wallets.serializers import (
    WalletSerializer,
    WalletTransactionSerializer,
    WalletListSerializer,
    MainToBbpsTransferSerializer,
)
from apps.wallets.services import transfer_main_to_bbps
from apps.core.financial_access import assert_can_perform_financial_txn
from apps.core.exceptions import InsufficientBalance


def _normalize_wallet_type(raw_wallet_type: str) -> str:
    wt = str(raw_wallet_type or '').strip().lower().replace(' ', '').replace('_', '')
    aliases = {
        'main': 'main',
        'mainwallet': 'main',
        'commission': 'commission',
        'commissionwallet': 'commission',
        'bbps': 'bbps',
        'bbpswallet': 'bbps',
        'profit': 'profit',
        'profitwallet': 'profit',
    }
    return aliases.get(wt, wt)


def _passbook_rows_for_wallet_history(user, wallet_type: str, page: int, page_size: int):
    entries = (
        PassbookEntry.objects.filter(user=user, wallet_type=wallet_type)
        .order_by('-created_at')
    )
    start = (page - 1) * page_size
    end = start + page_size
    rows = []
    for e in entries[start:end]:
        credit = e.credit_amount or 0
        debit = e.debit_amount or 0
        tx_type = 'credit' if credit and credit > 0 else 'debit'
        amount = credit if tx_type == 'credit' else debit
        src_user_code = (e.initiator_user_code or '').strip()
        src_role = (e.initiator_role_at_time or '').strip()
        src_name = (e.initiator_name_snapshot or '').strip()
        rows.append(
            {
                'id': f'pb-{e.id}',
                'wallet': None,
                'amount': str(amount),
                'transaction_type': tx_type,
                'reference': e.service_id,
                'description': e.description,
                'created_at': e.created_at,
                'service': e.service,
                'service_id': e.service_id,
                'source_user_code': src_user_code,
                'source_role': src_role,
                'source_name': src_name,
            }
        )
    return rows, entries.count()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def transfer_main_to_bbps_view(request):
    """
    POST /api/wallets/transfer-to-bbps/
    Body: { "amount": "100.00", "mpin": "123456" }
    """
    assert_can_perform_financial_txn(request.user)
    serializer = MainToBbpsTransferSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not request.user.check_mpin(serializer.validated_data['mpin']):
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Invalid MPIN',
                'errors': {'mpin': ['Invalid MPIN']},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        out = transfer_main_to_bbps(request.user, serializer.validated_data['amount'])
    except ValueError as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e), 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except InsufficientBalance as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e), 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {
            'success': True,
            'data': out,
            'message': 'Transferred to BBPS wallet',
            'errors': [],
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_wallets_view(request):
    """
    Get all wallets for the authenticated user.
    GET /api/wallets/
    """
    wallets = Wallet.objects.filter(user=request.user)
    
    # Organize wallets by type
    wallet_dict = {}
    for wallet in wallets:
        wallet_dict[wallet.wallet_type] = WalletSerializer(wallet).data
    
    # Ensure all wallet types are present
    wallet_data = {
        'main': wallet_dict.get('main', {'balance': '0.00'}),
        'commission': wallet_dict.get('commission', {'balance': '0.00'}),
        'bbps': wallet_dict.get('bbps', {'balance': '0.00'}),
        'profit': wallet_dict.get('profit', {'balance': '0.00'}),
    }
    
    return Response({
        'success': True,
        'data': {'wallets': wallet_data},
        'message': 'Wallets retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_wallet_view(request, wallet_type):
    """
    Get specific wallet for the authenticated user.
    GET /api/wallets/{type}/
    """
    try:
        wallet = Wallet.get_wallet(request.user, wallet_type)
        serializer = WalletSerializer(wallet)
        return Response({
            'success': True,
            'data': {'wallet': serializer.data},
            'message': 'Wallet retrieved successfully',
            'errors': []
        }, status=status.HTTP_200_OK)
    except ValueError:
        return Response({
            'success': False,
            'data': None,
            'message': 'Invalid wallet type',
            'errors': []
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_wallet_history_view(request, wallet_type):
    """
    Get transaction history for a specific wallet.
    GET /api/wallets/{type}/history/
    """
    try:
        normalized_wallet_type = _normalize_wallet_type(wallet_type)
        wallet = Wallet.get_wallet(request.user, normalized_wallet_type)

        # Get transactions with pagination
        transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')

        # Apply pagination
        page_size = 20
        page = max(1, int(request.query_params.get('page', 1)))
        start = (page - 1) * page_size
        end = start + page_size

        total = transactions.count()
        if total > 0:
            paginated_transactions = transactions[start:end]
            serializer = WalletTransactionSerializer(paginated_transactions, many=True)
            tx_rows = serializer.data
        else:
            # Fallback for legacy rows where only passbook lines exist.
            tx_rows, total = _passbook_rows_for_wallet_history(request.user, normalized_wallet_type, page, page_size)

        return Response({
            'success': True,
            'data': {
                'transactions': tx_rows,
                'total': total,
                'page': page,
                'page_size': page_size
            },
            'message': 'Wallet history retrieved successfully',
            'errors': []
        }, status=status.HTTP_200_OK)
    except ValueError:
        return Response({
            'success': False,
            'data': None,
            'message': 'Invalid wallet type',
            'errors': []
        }, status=status.HTTP_400_BAD_REQUEST)
