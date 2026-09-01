"""User-facing views for manual QR pay-in."""
import mimetypes

from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.financial_access import assert_can_pay_in
from apps.core.maintenance_mode import MODULE_PAY_IN, assert_module_available
from apps.fund_management.models import LoadMoney, PayInQrAccount
from apps.fund_management.package_qr_accounts import list_checkout_qr_for_package
from apps.fund_management.qr_image import qr_image_file_response
from apps.fund_management.serializers import LoadMoneySerializer
from apps.fund_management.serializers_qr import PayInQrSubmitSerializer
from apps.fund_management.services_qr import submit_qr_payin
from apps.fund_management.services import get_user_accessible_packages


def _user_can_view_qr_account(user, qr_account_id: int) -> bool:
    if getattr(user, 'role', None) == 'Admin':
        return True
    for package in get_user_accessible_packages(user):
        for qr in list_checkout_qr_for_package(package):
            if qr.pk == qr_account_id:
                return True
    return False


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pay_in_qr_account_image_view(request, qr_account_id: int):
    """GET QR image for checkout (JWT required — use AuthenticatedImage on frontend)."""
    assert_can_pay_in(request.user)
    assert_module_available(MODULE_PAY_IN)
    qr = PayInQrAccount.objects.filter(pk=qr_account_id, is_deleted=False, status='active').first()
    if not qr or not qr.qr_image:
        raise Http404
    if not _user_can_view_qr_account(request.user, qr_account_id):
        raise Http404
    return qr_image_file_response(qr.qr_image, download_name=f'qr-{qr.pk}.png')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def pay_in_qr_submit_view(request):
    """POST /api/fund-management/pay-in/qr/submit/ — multipart QR proof submission."""
    assert_can_pay_in(request.user)
    assert_module_available(MODULE_PAY_IN)
    ser = PayInQrSubmitSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        lm = submit_qr_payin(
            user=request.user,
            package_id=ser.validated_data['package_id'],
            qr_account_id=ser.validated_data['qr_account_id'],
            contact_id=ser.validated_data['contact_id'],
            amount=ser.validated_data['amount'],
            utr=ser.validated_data['utr'],
            payment_date=ser.validated_data['payment_date'],
            receipt_file=ser.validated_data['receipt'],
        )
    except Exception as exc:
        from rest_framework.exceptions import ValidationError

        if isinstance(exc, ValidationError):
            detail = exc.detail
            msg = detail.get('utr', detail) if isinstance(detail, dict) else str(detail)
            if isinstance(msg, list):
                msg = msg[0] if msg else 'Validation failed'
            return Response(
                {'success': False, 'data': None, 'message': str(msg), 'errors': detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raise

    return Response(
        {
            'success': True,
            'data': {'load_money': LoadMoneySerializer(lm, context={'request': request}).data},
            'message': 'Request submitted. Wallet will be credited after verification.',
            'errors': [],
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pay_in_qr_receipt_view(request, transaction_id: str):
    """GET receipt image for owner or admin."""
    lm = (
        LoadMoney.objects.filter(transaction_id=transaction_id, collection_rail='qr', is_deleted=False)
        .select_related('user')
        .first()
    )
    if not lm or not lm.receipt_image:
        raise Http404
    is_admin = getattr(request.user, 'role', None) == 'Admin'
    if not is_admin and lm.user_id != request.user.id:
        raise Http404
    try:
        fh = lm.receipt_image.open('rb')
        name = lm.receipt_image.name.rsplit('/', 1)[-1] if lm.receipt_image.name else 'receipt.jpg'
        content_type = mimetypes.guess_type(name)[0] or 'image/jpeg'
        response = FileResponse(fh, content_type=content_type)
        if request.GET.get('download') in ('1', 'true', 'yes'):
            if not name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                name = f'receipt-{transaction_id}.jpg'
            response['Content-Disposition'] = f'attachment; filename="{name}"'
        return response
    except Exception as exc:
        raise Http404 from exc
