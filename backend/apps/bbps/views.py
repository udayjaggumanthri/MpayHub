"""
BBPS views for the mPayhub platform.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.bbps.models import BillPayment
from apps.bbps.serializers import (
    BillerSerializer,
    BillSerializer,
    BillPaymentSerializer,
    FetchBillSerializer,
    BillPaymentCreateSerializer
)
from apps.bbps.services import (
    fetch_bill,
    process_bill_payment,
    get_bill_categories,
    get_billers_by_category
)
from apps.core.exceptions import InsufficientBalance, TransactionFailed


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_categories_view(request):
    """
    Get bill categories.
    GET /api/bbps/categories/
    """
    categories = get_bill_categories()
    return Response({
        'success': True,
        'data': {'categories': categories},
        'message': 'Categories retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_billers_view(request, category):
    """
    Get billers for a category.
    GET /api/bbps/billers/{category}/
    """
    billers = get_billers_by_category(category)
    serializer = BillerSerializer(billers, many=True)
    return Response({
        'success': True,
        'data': {'billers': serializer.data},
        'message': 'Billers retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def fetch_bill_view(request):
    """
    Fetch bill details.
    POST /api/bbps/fetch-bill/
    """
    serializer = FetchBillSerializer(data=request.data)
    if serializer.is_valid():
        try:
            bill = fetch_bill(
                serializer.validated_data['biller'],
                serializer.validated_data['category'],
                **{k: v for k, v in serializer.validated_data.items() if k not in ['biller', 'category']}
            )
            bill_serializer = BillSerializer(bill)
            return Response({
                'success': True,
                'data': {'bill': bill_serializer.data},
                'message': 'Bill fetched successfully',
                'errors': []
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'data': None,
                'message': f'Failed to fetch bill: {str(e)}',
                'errors': []
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'success': False,
        'data': None,
        'message': 'Failed to fetch bill',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pay_bill_view(request):
    """
    Process bill payment.
    POST /api/bbps/pay/
    """
    serializer = BillPaymentCreateSerializer(data=request.data)
    if serializer.is_valid():
        try:
            bill_payment = process_bill_payment(request.user, serializer.validated_data)
            response_data = BillPaymentSerializer(bill_payment).data
            return Response({
                'success': True,
                'data': {'bill_payment': response_data},
                'message': 'Bill payment processed successfully',
                'errors': []
            }, status=status.HTTP_201_CREATED)
        except (InsufficientBalance, TransactionFailed) as e:
            return Response({
                'success': False,
                'data': None,
                'message': str(e),
                'errors': []
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'success': False,
        'data': None,
        'message': 'Bill payment failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bill_payments_list_view(request):
    """
    List bill payments (My Bills).
    GET /api/bbps/payments/
    """
    payments = BillPayment.objects.filter(user=request.user).order_by('-created_at')
    
    # Filters
    status_filter = request.query_params.get('status')
    if status_filter:
        payments = payments.filter(status=status_filter)
    
    # Pagination
    page_size = 20
    page = int(request.query_params.get('page', 1))
    start = (page - 1) * page_size
    end = start + page_size
    
    paginated_payments = payments[start:end]
    serializer = BillPaymentSerializer(paginated_payments, many=True)
    
    return Response({
        'success': True,
        'data': {
            'payments': serializer.data,
            'total': payments.count(),
            'page': page,
            'page_size': page_size
        },
        'message': 'Bill payments retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bill_payment_detail_view(request, payment_id):
    """
    Get bill payment details.
    GET /api/bbps/payments/{id}/
    """
    try:
        payment = BillPayment.objects.get(id=payment_id, user=request.user)
        serializer = BillPaymentSerializer(payment)
        return Response({
            'success': True,
            'data': {'payment': serializer.data},
            'message': 'Bill payment retrieved successfully',
            'errors': []
        }, status=status.HTTP_200_OK)
    except BillPayment.DoesNotExist:
        return Response({
            'success': False,
            'data': None,
            'message': 'Bill payment not found',
            'errors': []
        }, status=status.HTTP_404_NOT_FOUND)
