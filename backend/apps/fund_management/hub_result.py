"""Signed result endpoint. Settlement stays in finalize_payin_success."""

import hashlib
import hmac
import json
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.fund_management.models import LoadMoney
from apps.fund_management.payin_settlement import finalize_payin_success


def _signature_ok(request):
    timestamp = request.headers.get('X-Hub-Timestamp', '')
    signature = request.headers.get('X-Hub-Signature', '')
    if not timestamp or not signature:
        return False
    body = request.body or b''
    for secret in _result_secrets():
        expected = hmac.new(
            secret.encode('utf-8'),
            f'{timestamp}.'.encode('utf-8') + body,
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(expected, signature.strip()):
            return True
    return False


def _result_secrets():
    found = []
    env_secret = (os.getenv('PAYMENT_HUB_HMAC_SECRET') or '').strip()
    if env_secret:
        found.append(env_secret)
    try:
        from apps.core.utils import decrypt_secret_payload
        from apps.integrations.models import ApiMaster

        rows = ApiMaster.objects.filter(
            provider_type='payments',
            provider_code='toucan',
            is_deleted=False,
            status__in=['active', 'sandbox'],
        )
        for row in rows:
            secrets = decrypt_secret_payload(row.secrets_encrypted or '') or {}
            secret = str(secrets.get('hmac_secret') or '').strip()
            if secret and secret not in found:
                found.append(secret)
    except Exception:
        pass
    return found


@csrf_exempt
def payment_result_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    if not _signature_ok(request):
        return JsonResponse({'error': 'Rejected result.'}, status=401)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid result.'}, status=400)

    reference = str(payload.get('application_order_id') or '')
    load_money = LoadMoney.objects.filter(transaction_id=reference).first()
    if load_money is None:
        return JsonResponse({'error': 'Pay-in not found.'}, status=404)

    status = payload.get('payment_status')
    if status == 'SUCCESS':
        finalize_payin_success(
            load_money,
            provider_payment_id=str(payload.get('invoice') or '') or None,
            gateway_reference=str(payload.get('provider_reference') or payload.get('invoice') or ''),
            payment_method='toucan',
            payment_meta=payload.get('provider_metadata') or {},
        )
    elif status in ('FAILED', 'CANCELLED') and load_money.status != 'SUCCESS':
        load_money.status = 'FAILED'
        load_money.failure_reason = 'Payment was not completed'
        load_money.save(update_fields=['status', 'failure_reason'])
    return JsonResponse({'ok': True})
