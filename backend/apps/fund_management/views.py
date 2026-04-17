"""
Fund management views for the mPayhub platform.
"""
import logging
from decimal import Decimal

from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import InsufficientBalance, TransactionFailed
from apps.core.financial_access import assert_can_perform_financial_txn
from apps.fund_management.models import LoadMoney, PayInPackage, Payout
from apps.fund_management.serializers import (
    LegacyLoadMoneyCreateSerializer,
    LoadMoneySerializer,
    PayInCreateOrderSerializer,
    PayInMockCompleteSerializer,
    PayInPackageSerializer,
    PayInQuoteSerializer,
    PayInRazorpayVerifySerializer,
    PayoutSerializer,
)
from apps.fund_management.services import (
    assign_package_to_user,
    complete_mock_payin,
    create_payin_order,
    get_assignable_packages_for_user,
    get_available_gateways,
    get_user_accessible_packages,
    get_user_assigned_packages,
    list_active_pay_in_packages,
    max_payout_eligible,
    payout_slab_charge,
    process_load_money,
    process_payout,
    quote_payin,
    remove_package_assignment,
    verify_and_finalize_razorpay_payin,
)

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pay_in_quote_view(request):
    """POST /api/fund-management/pay-in/quote/ — fee breakdown for a package + amount."""
    assert_can_perform_financial_txn(request.user)
    ser = PayInQuoteSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    pkg = PayInPackage.objects.filter(
        id=ser.validated_data['package_id'], is_active=True, is_deleted=False
    ).first()
    if not pkg:
        return Response(
            {'success': False, 'data': None, 'message': 'Package not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        q = quote_payin(pkg, ser.validated_data['amount'], request.user)
    except ValueError as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e), 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {
            'success': True,
            'data': {
                'breakdown': q['snapshot'],
                'lines': q['lines'],
                'net_credit': str(q['net_credit']),
                'total_deduction': str(q['total_deduction']),
                'retailer_commission': str(q['retailer_commission']),
                'retailer_share_absorbed_to_admin': str(q['retailer_share_absorbed_to_admin']),
            },
            'message': 'OK',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pay_in_create_order_view(request):
    """POST /api/fund-management/pay-in/create-order/"""
    assert_can_perform_financial_txn(request.user)
    ser = PayInCreateOrderSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        lm, payload = create_payin_order(
            request.user,
            package_id=ser.validated_data['package_id'],
            gross=ser.validated_data['amount'],
            contact_id=ser.validated_data['contact_id'],
        )
    except ValueError as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e), 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except TransactionFailed as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e), 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )
    payload['load_money'] = LoadMoneySerializer(lm).data
    return Response(
        {'success': True, 'data': payload, 'message': 'Order created', 'errors': []},
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pay_in_complete_mock_view(request):
    """POST /api/fund-management/pay-in/complete-mock/ — dev/mock provider only."""
    assert_can_perform_financial_txn(request.user)
    ser = PayInMockCompleteSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        lm = complete_mock_payin(request.user, ser.validated_data['transaction_id'])
    except ValueError as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e), 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except TransactionFailed as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e), 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {
            'success': True,
            'data': {'load_money': LoadMoneySerializer(lm).data},
            'message': 'Payment completed',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pay_in_verify_razorpay_view(request):
    """POST /api/fund-management/pay-in/verify-razorpay/ — confirm checkout + credit wallet."""
    assert_can_perform_financial_txn(request.user)
    ser = PayInRazorpayVerifySerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    d = ser.validated_data
    try:
        lm = verify_and_finalize_razorpay_payin(
            request.user,
            transaction_id=d['transaction_id'],
            razorpay_order_id=d['razorpay_order_id'],
            razorpay_payment_id=d['razorpay_payment_id'],
            razorpay_signature=d['razorpay_signature'],
        )
    except ValueError as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e), 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except TransactionFailed as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e), 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.exception(
            (
                'Unexpected Razorpay verify failure '
                'transaction_id=%s order_id=%s payment_id=%s user_id=%s'
            ),
            d.get('transaction_id'),
            d.get('razorpay_order_id'),
            d.get('razorpay_payment_id'),
            request.user.id,
        )
        return Response(
            {
                'success': False,
                'data': None,
                'message': f'Could not confirm payment: {e}',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {
            'success': True,
            'data': {'load_money': LoadMoneySerializer(lm).data},
            'message': 'Payment verified and wallet updated',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pay_in_packages_view(request):
    """
    GET /api/fund-management/pay-in/packages/
    
    Returns packages accessible to the current user:
    - Admin: all active packages
    - Non-admin: packages explicitly assigned to them, or default package if none assigned
    
    Query params:
    - all=true: (Admin only) return all active packages regardless of assignment
    """
    all_param = request.query_params.get('all', '').lower() == 'true'
    user_role = (getattr(request.user, 'role', None) or '').strip()
    
    if all_param and user_role == 'Admin':
        pkgs = list_active_pay_in_packages()
    else:
        pkgs = get_user_accessible_packages(request.user)
    
    return Response(
        {
            'success': True,
            'data': {'packages': PayInPackageSerializer(pkgs, many=True).data},
            'message': 'OK',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payout_quote_view(request):
    """GET /api/fund-management/payout/quote/?amount= optional — max eligible + slab preview."""
    assert_can_perform_financial_txn(request.user)
    from django.conf import settings
    from apps.wallets.models import Wallet

    main = Wallet.get_wallet(request.user, 'main')
    balance = main.balance
    max_el = max_payout_eligible(balance)
    out = {
        'main_balance': str(balance),
        'max_eligible_amount': str(max_el),
        'slab_low_max': str(settings.PAYOUT_SLAB_LOW_MAX),
        'charge_low': str(settings.PAYOUT_CHARGE_LOW),
        'charge_high': str(settings.PAYOUT_CHARGE_HIGH),
    }
    amt_param = request.query_params.get('amount')
    if amt_param:
        try:
            amt = money_q_local(Decimal(str(amt_param)))
            ch = payout_slab_charge(amt)
            out['preview'] = {
                'amount': str(amt),
                'charge': str(ch),
                'total_debit': str(money_q_local(amt + ch)),
            }
        except Exception:
            pass
    return Response(
        {'success': True, 'data': out, 'message': 'OK', 'errors': []},
        status=status.HTTP_200_OK,
    )


def money_q_local(v):
    return v.quantize(Decimal('0.0001'))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def load_money_view(request):
    """
    Initiate load money transaction (legacy immediate success).
    POST /api/fund-management/load-money/
    """
    serializer = LegacyLoadMoneyCreateSerializer(data=request.data)
    if serializer.is_valid():
        try:
            amount = serializer.validated_data['amount']
            gateway_id = serializer.validated_data.get('gateway')
            load_money = process_load_money(request.user, amount, gateway_id)
            response_data = LoadMoneySerializer(load_money).data
            return Response(
                {
                    'success': True,
                    'data': {'load_money': response_data},
                    'message': 'Load money initiated successfully',
                    'errors': [],
                },
                status=status.HTTP_201_CREATED,
            )
        except TransactionFailed as e:
            return Response(
                {'success': False, 'data': None, 'message': str(e), 'errors': []},
                status=status.HTTP_400_BAD_REQUEST,
            )
    return Response(
        {
            'success': False,
            'data': None,
            'message': 'Load money failed',
            'errors': serializer.errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def load_money_list_view(request):
    """
    List load money transactions for the authenticated user.
    GET /api/fund-management/load-money/list/

    Query: page, page_size (max 500), status (PENDING|SUCCESS|FAILED),
    search (transaction_id icontains), date_from, date_to (YYYY-MM-DD on created_at date).
    """
    from django.utils.dateparse import parse_date

    transactions = (
        LoadMoney.objects.filter(user=request.user)
        .select_related('package', 'package__payment_gateway')
        .order_by('-created_at')
    )

    raw_status = (request.query_params.get('status') or '').strip().upper()
    if raw_status and raw_status != 'ALL':
        if raw_status == 'FAILURE':
            raw_status = 'FAILED'
        if raw_status in ('PENDING', 'SUCCESS', 'FAILED'):
            transactions = transactions.filter(status=raw_status)

    search = (request.query_params.get('search') or '').strip()
    if search:
        transactions = transactions.filter(transaction_id__icontains=search)

    df = parse_date((request.query_params.get('date_from') or '').strip())
    if df:
        transactions = transactions.filter(created_at__date__gte=df)
    dt = parse_date((request.query_params.get('date_to') or '').strip())
    if dt:
        transactions = transactions.filter(created_at__date__lte=dt)

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
    serializer = LoadMoneySerializer(paginated_transactions, many=True)
    return Response(
        {
            'success': True,
            'data': {
                'transactions': serializer.data,
                'total': transactions.count(),
                'page': page,
                'page_size': page_size,
            },
            'message': 'Load money transactions retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def payout_view(request):
    """
    Initiate payout transaction.
    POST /api/fund-management/payout/
    """
    assert_can_perform_financial_txn(request.user)
    serializer = PayoutSerializer(data=request.data)
    if serializer.is_valid():
        vd = serializer.validated_data
        if not request.user.check_mpin(vd['mpin']):
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
            bank_account_id = vd['bank_account_id']
            amount = vd['amount']
            transfer_mode = vd.get('transfer_mode') or 'IMPS'
            gateway_id = vd.get('gateway')
            payout = process_payout(
                request.user,
                bank_account_id,
                amount,
                gateway_id=gateway_id,
                transfer_mode=transfer_mode,
            )
            response_data = PayoutSerializer(payout).data
            return Response(
                {
                    'success': True,
                    'data': {'payout': response_data},
                    'message': 'Payout initiated successfully',
                    'errors': [],
                },
                status=status.HTTP_201_CREATED,
            )
        except (InsufficientBalance, ValueError, TransactionFailed) as e:
            return Response(
                {'success': False, 'data': None, 'message': str(e), 'errors': []},
                status=status.HTTP_400_BAD_REQUEST,
            )
    return Response(
        {'success': False, 'data': None, 'message': 'Payout failed', 'errors': serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payout_list_view(request):
    """
    List payout transactions for the authenticated user.
    GET /api/fund-management/payout/list/

    Query: page, page_size (max 500), status, search (transaction_id icontains),
    date_from, date_to (YYYY-MM-DD).
    """
    transactions = Payout.objects.filter(user=request.user).select_related('bank_account').order_by('-created_at')

    raw_status = (request.query_params.get('status') or '').strip().upper()
    if raw_status and raw_status != 'ALL':
        if raw_status == 'FAILURE':
            raw_status = 'FAILED'
        if raw_status in ('PENDING', 'SUCCESS', 'FAILED'):
            transactions = transactions.filter(status=raw_status)

    search = (request.query_params.get('search') or '').strip()
    if search:
        transactions = transactions.filter(transaction_id__icontains=search)

    df = parse_date((request.query_params.get('date_from') or '').strip())
    if df:
        transactions = transactions.filter(created_at__date__gte=df)
    dt = parse_date((request.query_params.get('date_to') or '').strip())
    if dt:
        transactions = transactions.filter(created_at__date__lte=dt)

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
    serializer = PayoutSerializer(paginated_transactions, many=True)
    return Response(
        {
            'success': True,
            'data': {
                'transactions': serializer.data,
                'total': total,
                'page': page,
                'page_size': page_size,
            },
            'message': 'Payout transactions retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_gateways_view(request):
    """
    Get available payment/payout gateways for the user.
    GET /api/fund-management/gateways/?type=payment
    """
    assert_can_perform_financial_txn(request.user)
    gateway_type = request.query_params.get('type', 'payment')
    gateways = get_available_gateways(request.user.role, gateway_type)
    gateway_list = []
    for gateway in gateways:
        gateway_list.append(
            {
                'id': gateway.id,
                'name': gateway.name,
                'charge_rate': gateway.charge_rate if hasattr(gateway, 'charge_rate') else None,
                'status': gateway.status,
            }
        )
    return Response(
        {
            'success': True,
            'data': {'gateways': gateway_list},
            'message': 'Gateways retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Package Assignment Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_packages_view(request, user_id):
    """
    GET /api/fund-management/packages/user/<user_id>/
    
    Returns packages assigned to a specific user.
    Only Admin or the user's upline can view this.
    """
    from apps.authentication.models import User
    from apps.fund_management.services import is_user_in_downline

    try:
        target_user = User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return Response(
            {'success': False, 'data': None, 'message': 'User not found.', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        requester = request.user
        requester_role = (getattr(requester, 'role', None) or '').strip()

        # Permission check: Admin, self, or upline
        can_view = (
            requester_role == 'Admin'
            or requester.pk == target_user.pk
            or is_user_in_downline(requester, target_user)
        )
        if not can_view:
            return Response(
                {'success': False, 'data': None, 'message': 'Permission denied.', 'errors': []},
                status=status.HTTP_403_FORBIDDEN,
            )

        assigned_packages = get_user_assigned_packages(target_user)
        accessible_packages = get_user_accessible_packages(target_user)

        return Response(
            {
                'success': True,
                'data': {
                    'user_id': target_user.pk,
                    'user_code': str(target_user.user_id),
                    'assigned_packages': PayInPackageSerializer(assigned_packages, many=True).data,
                    'accessible_packages': PayInPackageSerializer(accessible_packages, many=True).data,
                },
                'message': 'OK',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        logger.exception('Error in user_packages_view for user_id=%s: %s', user_id, str(e))
        return Response(
            {'success': False, 'data': None, 'message': f'Server error: {str(e)}', 'errors': []},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def assignable_packages_view(request):
    """
    GET /api/fund-management/packages/assignable/
    
    Returns packages that the current user can assign to their downline.
    Admin: all active packages
    Non-admin: only their assigned packages
    """
    packages = get_assignable_packages_for_user(request.user)
    return Response(
        {
            'success': True,
            'data': {'packages': PayInPackageSerializer(packages, many=True).data},
            'message': 'OK',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_package_view(request):
    """
    POST /api/fund-management/packages/assign/
    
    Assign a package to a user.
    Body: { user_id: int, package_id: int }
    
    Validation:
    - Assigner must have access to the package (or be Admin)
    - Target must be in assigner's downline (or assigner is Admin)
    """
    from apps.authentication.models import User

    user_id = request.data.get('user_id')
    package_id = request.data.get('package_id')

    if not user_id or not package_id:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'user_id and package_id are required.',
                'errors': {'user_id': ['Required'], 'package_id': ['Required']},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        target_user = User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return Response(
            {'success': False, 'data': None, 'message': 'User not found.', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        result = assign_package_to_user(
            assigner=request.user,
            target_user=target_user,
            package_id=package_id,
        )

        if not result['success']:
            return Response(
                {'success': False, 'data': None, 'message': result['message'], 'errors': []},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment = result['assignment']
        return Response(
            {
                'success': True,
                'data': {
                    'assignment': {
                        'id': assignment.pk,
                        'user_id': assignment.user_id,
                        'package_id': assignment.package_id,
                        'package_name': assignment.package.display_name,
                        'assigned_by_id': assignment.assigned_by_id,
                    },
                },
                'message': result['message'],
                'errors': [],
            },
            status=status.HTTP_201_CREATED,
        )
    except Exception as e:
        logger.exception('Error in assign_package_view: user_id=%s, package_id=%s: %s', user_id, package_id, str(e))
        return Response(
            {'success': False, 'data': None, 'message': f'Server error: {str(e)}', 'errors': []},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_package_assignment_view(request):
    """
    POST /api/fund-management/packages/unassign/
    
    Remove a package assignment from a user.
    Body: { user_id: int, package_id: int }
    
    Only Admin, original assigner, or upline can remove.
    """
    from apps.authentication.models import User

    user_id = request.data.get('user_id')
    package_id = request.data.get('package_id')

    if not user_id or not package_id:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'user_id and package_id are required.',
                'errors': {'user_id': ['Required'], 'package_id': ['Required']},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        target_user = User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return Response(
            {'success': False, 'data': None, 'message': 'User not found.', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )

    result = remove_package_assignment(
        remover=request.user,
        target_user=target_user,
        package_id=package_id,
    )

    if not result['success']:
        return Response(
            {'success': False, 'data': None, 'message': result['message'], 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {'success': True, 'data': None, 'message': result['message'], 'errors': []},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_default_package_view(request):
    """
    POST /api/fund-management/packages/set-default/
    
    Set a package as the default (Admin only).
    Body: { package_id: int }
    
    Only one package can be default at a time.
    """
    requester_role = (getattr(request.user, 'role', None) or '').strip()
    if requester_role != 'Admin':
        return Response(
            {'success': False, 'data': None, 'message': 'Admin access required.', 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )

    package_id = request.data.get('package_id')
    if not package_id:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'package_id is required.',
                'errors': {'package_id': ['Required']},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    package = PayInPackage.objects.filter(pk=package_id, is_deleted=False).first()
    if not package:
        return Response(
            {'success': False, 'data': None, 'message': 'Package not found.', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Setting is_default=True will auto-clear other defaults in model.save()
    package.is_default = True
    package.save(update_fields=['is_default', 'updated_at'])

    logger.info(
        'Default package set: package=%s (%s) by admin=%s',
        package.pk,
        package.display_name,
        request.user.user_id,
    )

    return Response(
        {
            'success': True,
            'data': {'package': PayInPackageSerializer(package).data},
            'message': f'"{package.display_name}" is now the default package.',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_default_package_view(request):
    """
    POST /api/fund-management/packages/clear-default/
    
    Clear the default package (Admin only).
    No package will be auto-assigned to new users.
    """
    requester_role = (getattr(request.user, 'role', None) or '').strip()
    if requester_role != 'Admin':
        return Response(
            {'success': False, 'data': None, 'message': 'Admin access required.', 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )

    updated = PayInPackage.objects.filter(is_default=True).update(is_default=False)

    if updated:
        logger.info('Default package cleared by admin=%s', request.user.user_id)
        return Response(
            {'success': True, 'data': None, 'message': 'Default package cleared.', 'errors': []},
            status=status.HTTP_200_OK,
        )
    else:
        return Response(
            {'success': True, 'data': None, 'message': 'No default package was set.', 'errors': []},
            status=status.HTTP_200_OK,
        )
