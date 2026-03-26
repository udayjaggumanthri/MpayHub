"""
Fund management views for the mPayhub platform.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.fund_management.models import LoadMoney, Payout
from apps.fund_management.serializers import LoadMoneySerializer, PayoutSerializer
from apps.fund_management.services import (
    process_load_money,
    process_payout,
    get_available_gateways
)
from apps.core.exceptions import InsufficientBalance, TransactionFailed


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def load_money_view(request):
    """
    Initiate load money transaction.
    POST /api/fund-management/load-money/
    """
    serializer = LoadMoneySerializer(data=request.data)
    if serializer.is_valid():
        try:
            amount = serializer.validated_data['amount']
            gateway_id = serializer.validated_data.get('gateway')
            
            load_money = process_load_money(request.user, amount, gateway_id)
            response_data = LoadMoneySerializer(load_money).data
            
            return Response({
                'success': True,
                'data': {'load_money': response_data},
                'message': 'Load money initiated successfully',
                'errors': []
            }, status=status.HTTP_201_CREATED)
        except TransactionFailed as e:
            return Response({
                'success': False,
                'data': None,
                'message': str(e),
                'errors': []
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'success': False,
        'data': None,
        'message': 'Load money failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def load_money_list_view(request):
    """
    List load money transactions for the authenticated user.
    GET /api/fund-management/load-money/
    """
    transactions = LoadMoney.objects.filter(user=request.user).order_by('-created_at')
    
    # Pagination
    page_size = 20
    page = int(request.query_params.get('page', 1))
    start = (page - 1) * page_size
    end = start + page_size
    
    paginated_transactions = transactions[start:end]
    serializer = LoadMoneySerializer(paginated_transactions, many=True)
    
    return Response({
        'success': True,
        'data': {
            'transactions': serializer.data,
            'total': transactions.count(),
            'page': page,
            'page_size': page_size
        },
        'message': 'Load money transactions retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def payout_view(request):
    """
    Initiate payout transaction.
    POST /api/fund-management/payout/
    """
    serializer = PayoutSerializer(data=request.data)
    if serializer.is_valid():
        try:
            bank_account_id = serializer.validated_data['bank_account_id']
            amount = serializer.validated_data['amount']
            gateway_id = serializer.validated_data.get('gateway')
            
            payout = process_payout(request.user, bank_account_id, amount, gateway_id)
            response_data = PayoutSerializer(payout).data
            
            return Response({
                'success': True,
                'data': {'payout': response_data},
                'message': 'Payout initiated successfully',
                'errors': []
            }, status=status.HTTP_201_CREATED)
        except (InsufficientBalance, ValueError, TransactionFailed) as e:
            return Response({
                'success': False,
                'data': None,
                'message': str(e),
                'errors': []
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'success': False,
        'data': None,
        'message': 'Payout failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payout_list_view(request):
    """
    List payout transactions for the authenticated user.
    GET /api/fund-management/payout/
    """
    transactions = Payout.objects.filter(user=request.user).order_by('-created_at')
    
    # Pagination
    page_size = 20
    page = int(request.query_params.get('page', 1))
    start = (page - 1) * page_size
    end = start + page_size
    
    paginated_transactions = transactions[start:end]
    serializer = PayoutSerializer(paginated_transactions, many=True)
    
    return Response({
        'success': True,
        'data': {
            'transactions': serializer.data,
            'total': transactions.count(),
            'page': page,
            'page_size': page_size
        },
        'message': 'Payout transactions retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_gateways_view(request):
    """
    Get available payment/payout gateways for the user.
    GET /api/fund-management/gateways/?type=payment
    """
    gateway_type = request.query_params.get('type', 'payment')
    gateways = get_available_gateways(request.user.role, gateway_type)
    
    gateway_list = []
    for gateway in gateways:
        gateway_list.append({
            'id': gateway.id,
            'name': gateway.name,
            'charge_rate': gateway.charge_rate if hasattr(gateway, 'charge_rate') else None,
            'status': gateway.status
        })
    
    return Response({
        'success': True,
        'data': {'gateways': gateway_list},
        'message': 'Gateways retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)
