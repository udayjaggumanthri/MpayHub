"""
Webhooks and provider callbacks (no session auth).
"""
import json
import logging
import requests

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin
from apps.fund_management.models import LoadMoney
from apps.core.exceptions import TransactionFailed
from apps.fund_management.services import finalize_payin_success
from apps.integrations.models import ApiMaster
from apps.core.utils import decrypt_secret_payload
from apps.integrations.razorpay_orders import (
    extract_razorpay_key_pair_from_secrets,
    is_razorpay_like_provider_code,
    parse_order_paid_event,
    parse_payment_captured_event,
    resolve_razorpay_credentials,
    verify_razorpay_basic_auth,
    verify_webhook_signature,
)
from apps.integrations.serializers import ApiMasterSerializer

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        body = request.body
        sig = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
        if not verify_webhook_signature(body, sig):
            logger.warning(
                'Razorpay webhook signature failed — set RAZORPAY_WEBHOOK_SECRET to the signing secret '
                'from Razorpay Dashboard → Webhooks (API key secret often does not match).'
            )
            return Response({'success': False}, status=400)
        try:
            data = json.loads(body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response({'success': False}, status=400)

        event = data.get('event') or ''
        order_id = payment_id = None
        pay_method = None
        pay_meta = {}

        if event == 'payment.captured':
            order_id, payment_id, pay_method, pay_meta = parse_payment_captured_event(data)
        elif event == 'order.paid':
            order_id, payment_id, pay_method, pay_meta = parse_order_paid_event(data)
        else:
            return Response({'success': True, 'ignored': event})

        if not order_id or not payment_id:
            return Response({'success': True, 'message': 'no order/payment id'})

        try:
            with transaction.atomic():
                lm = (
                    LoadMoney.objects.select_for_update()
                    .filter(provider_order_id=order_id, status='PENDING')
                    .first()
                )
                if not lm:
                    return Response({'success': True, 'message': 'order not pending'})
                finalize_payin_success(
                    lm,
                    provider_payment_id=payment_id,
                    gateway_reference=payment_id,
                    payment_method=pay_method,
                    payment_meta=pay_meta or None,
                )
                logger.info(
                    'Razorpay webhook %s applied: order_id=%s payment_id=%s load_money_id=%s',
                    event,
                    order_id,
                    payment_id,
                    lm.pk,
                )
        except TransactionFailed as e:
            logger.exception('finalize pay-in failed: %s', e)
            return Response({'success': False}, status=400)
        return Response({'success': True})


@method_decorator(csrf_exempt, name='dispatch')
class PayUWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        logger.info('PayU webhook stub — extend with hash verification')
        return Response({'success': True, 'message': 'not_implemented'})


class ApiMasterViewSet(viewsets.ModelViewSet):
    """Admin API master CRUD (enterprise integration registry)."""

    queryset = ApiMaster.objects.filter(is_deleted=False).order_by('provider_type', '-is_default', 'priority')
    serializer_class = ApiMasterSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_default and instance.status == 'active':
            has_other_active_default = ApiMaster.objects.filter(
                provider_type=instance.provider_type,
                is_default=True,
                status='active',
                is_deleted=False,
            ).exclude(pk=instance.pk).exists()
            if not has_other_active_default:
                return Response(
                    {
                        'success': False,
                        'message': 'Cannot delete the only active default config for this provider type.',
                        'errors': [],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        src = self.get_object()
        clone = ApiMaster.objects.create(
            provider_code=f"{src.provider_code}-sandbox-{src.pk}",
            provider_name=f"{src.provider_name} (Sandbox)",
            provider_type=src.provider_type,
            base_url=src.base_url,
            auth_type=src.auth_type,
            config_json=src.config_json,
            secrets_encrypted=src.secrets_encrypted,
            status='sandbox',
            priority=src.priority,
            is_default=False,
            supports_webhook=src.supports_webhook,
            webhook_path=src.webhook_path,
        )
        ser = self.get_serializer(clone)
        return Response(
            {'success': True, 'data': {'api_master': ser.data}, 'message': 'Cloned', 'errors': []},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        obj = self.get_object()
        timeout = int((obj.config_json or {}).get('timeout', 8))
        timeout = max(3, min(timeout, 45))

        # Razorpay: verify real API credentials (generic HTTP ping does not use key_id/key_secret).
        if is_razorpay_like_provider_code(obj.provider_code):
            payload = decrypt_secret_payload(obj.secrets_encrypted or '')
            from_blob = extract_razorpay_key_pair_from_secrets(payload)
            ok, status_code, detail = verify_razorpay_basic_auth(from_blob[0], from_blob[1], timeout=timeout)
            resolved = resolve_razorpay_credentials(from_blob[0], from_blob[1])
            creds_from_blob = bool(from_blob[0] and from_blob[1])
            creds_from_env = bool(resolved[0] and resolved[1]) and not creds_from_blob
            return Response(
                {
                    'success': ok,
                    'data': {
                        'status_code': status_code,
                        'ok': ok,
                        'razorpay_auth': True,
                        'detail': detail if not ok else 'Credentials accepted by Razorpay API',
                        'credentials_from_api_master': creds_from_blob,
                        'credentials_from_env_fallback': creds_from_env,
                    },
                    'message': 'Razorpay credentials verified' if ok else f'Razorpay auth failed: {detail}',
                    'errors': [] if ok else [str(detail)],
                },
                status=status.HTTP_200_OK if ok else status.HTTP_400_BAD_REQUEST,
            )

        method = str((obj.config_json or {}).get('test_method', 'GET')).upper()
        endpoint = str((obj.config_json or {}).get('test_path', '')).strip()
        url = f"{obj.base_url.rstrip('/')}/{endpoint.lstrip('/')}" if endpoint else obj.base_url
        if not url:
            return Response(
                {'success': False, 'message': 'Base URL missing', 'errors': []},
                status=status.HTTP_400_BAD_REQUEST,
            )
        headers = {'User-Agent': 'mPayhub-api-master-test/1.0'}
        try:
            if method == 'POST':
                resp = requests.post(url, timeout=timeout, headers=headers, json={})
            else:
                resp = requests.get(url, timeout=timeout, headers=headers)
            ok = 200 <= resp.status_code < 500
            return Response(
                {
                    'success': ok,
                    'data': {
                        'status_code': resp.status_code,
                        'ok': ok,
                        'url': url,
                    },
                    'message': 'Connection tested',
                    'errors': [] if ok else ['Unexpected status code'],
                },
                status=status.HTTP_200_OK if ok else status.HTTP_400_BAD_REQUEST,
            )
        except requests.RequestException as e:
            return Response(
                {
                    'success': False,
                    'data': {'url': url},
                    'message': f'Connection failed: {e}',
                    'errors': [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
