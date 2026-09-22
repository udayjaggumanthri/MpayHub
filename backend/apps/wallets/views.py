"""
Wallet views for the mPayhub platform.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.core.permissions import IsAdmin
from apps.wallets.models import Wallet, WalletTransaction
from apps.transactions.models import PassbookEntry
from apps.wallets.serializers import (
    WalletSerializer,
    WalletTransactionSerializer,
    WalletListSerializer,
)
from apps.wallets.presentation import present_wallet_summary_for_viewer


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

    Deprecated after single-wallet consolidation. Returns HTTP 410.
    """
    return Response(
        {
            'success': False,
            'data': None,
            'message': (
                'Main-to-BBPS wallet transfer has been removed. '
                'All bill payments debit your main wallet directly.'
            ),
            'errors': [{'code': 'TRANSFER_REMOVED'}],
        },
        status=status.HTTP_410_GONE,
    )


def build_wallet_summary(user):
    """
    Return wallet balances for the viewer.

    Live money is only on ``main``. Legacy keys are omitted so clients cannot
    render separate BBPS / commission / profit cards.
    """
    wallets = Wallet.objects.filter(user=user, is_archived=False)
    wallet_dict = {wallet.wallet_type: WalletSerializer(wallet).data for wallet in wallets}
    main = wallet_dict.get('main')
    if main is None:
        main = {
            'balance': '0.00',
            'held_balance': '0.00',
            'available_balance': '0.00',
            'wallet_type': 'main',
        }
    return {'main': main}



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_wallets_view(request):
    """
    Get all wallets for the authenticated user.
    GET /api/wallets/

    Admin / Super Admin logins share the platform treasury Main wallet so every
    operator sees the same balance; Distributed Balance is the channel network total.
    """
    from apps.fund_management.platform_settlement import wallet_user_for_viewer

    personal = build_wallet_summary(wallet_user_for_viewer(request.user))
    wallet_data = present_wallet_summary_for_viewer(request.user, personal)
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


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def distributed_ledger_view(request):
    """
    GET /api/wallets/distributed/ledger/

    Role-filterable list of channel users with Main wallet balances
    (the Distributed Balance breakdown for Admin / Super Admin).
    """
    from apps.wallets.portfolio import list_distributed_ledger

    try:
        page = int(request.query_params.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.query_params.get('page_size', 25))
    except (TypeError, ValueError):
        page_size = 25

    include_ops = str(request.query_params.get('include_operators') or '').lower() in (
        '1', 'true', 'yes',
    )
    data = list_distributed_ledger(
        viewer=request.user,
        role=(request.query_params.get('role') or '').strip() or None,
        search=(request.query_params.get('search') or request.query_params.get('q') or '').strip() or None,
        page=page,
        page_size=page_size,
        include_operators=include_ops,
    )
    return Response({
        'success': True,
        'data': data,
        'message': 'Distributed ledger retrieved',
        'errors': [],
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def distributed_network_view(request, user_id: int):
    """
    GET /api/wallets/distributed/network/<user_id>/

    Users managed under a distributor / SD / MD (or any network-capable role),
    with Main wallet balances.
    """
    from apps.wallets.portfolio import list_user_network_ledger

    try:
        page = int(request.query_params.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.query_params.get('page_size', 25))
    except (TypeError, ValueError):
        page_size = 25

    direct_only = str(request.query_params.get('direct_only') or '').lower() in (
        '1', 'true', 'yes',
    )
    data = list_user_network_ledger(
        manager_id=int(user_id),
        viewer=request.user,
        role=(request.query_params.get('role') or '').strip() or None,
        search=(request.query_params.get('search') or request.query_params.get('q') or '').strip() or None,
        page=page,
        page_size=page_size,
        direct_only=direct_only,
    )
    if data is None:
        return Response({
            'success': False,
            'data': None,
            'message': 'User not found',
            'errors': [],
        }, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'success': True,
        'data': data,
        'message': 'Network ledger retrieved',
        'errors': [],
    }, status=status.HTTP_200_OK)
