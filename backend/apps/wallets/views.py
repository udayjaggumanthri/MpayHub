"""
Wallet views for the mPayhub platform.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.wallets.models import Wallet, WalletTransaction
from apps.wallets.serializers import WalletSerializer, WalletTransactionSerializer, WalletListSerializer
from apps.core.permissions import IsOwner


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
        'bbps': wallet_dict.get('bbps', {'balance': '0.00'})
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
        wallet = Wallet.get_wallet(request.user, wallet_type)
        
        # Get transactions with pagination
        transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')
        
        # Apply pagination
        page_size = 20
        page = int(request.query_params.get('page', 1))
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_transactions = transactions[start:end]
        serializer = WalletTransactionSerializer(paginated_transactions, many=True)
        
        return Response({
            'success': True,
            'data': {
                'transactions': serializer.data,
                'total': transactions.count(),
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
