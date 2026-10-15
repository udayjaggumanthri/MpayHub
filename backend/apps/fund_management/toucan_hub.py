"""mPayHub client for the central payment hub. Live calls stay off until merchant approval."""

import hashlib
import hmac
import json
import logging
import os
import time
import urllib.error
import urllib.request

from apps.core.exceptions import TransactionFailed
from apps.fund_management.models import LoadMoney

logger = logging.getLogger(__name__)
HUB_USER_AGENT = 'mPayHub-PaymentHub/1.0'


def _hub_failure_reason(exc):
    if isinstance(exc, urllib.error.HTTPError):
        try:
            payload = json.loads(exc.read().decode('utf-8') or '{}')
        except Exception:
            payload = {}
        detail = str(payload.get('error') or '').strip()
        if detail:
            return detail[:240]
    return 'Payment hub did not open checkout.'


def hub_gate_open():
    return os.getenv('PAYMENT_HUB_TOUCAN_ENABLED', 'false').lower() in ('1', 'true', 'yes')


def start_toucan_payin(load_money, contact, response, *, base_url=None, api_key=None, hmac_secret=None):
    """Open a hub checkout. Explicit credentials skip the env gate; the API Master row is the switch."""
    from_registry = any(value is not None for value in (base_url, api_key, hmac_secret))
    if from_registry:
        base = (base_url or '').rstrip('/')
        key = api_key or ''
        secret = hmac_secret or ''
    else:
        if not hub_gate_open():
            LoadMoney.objects.filter(pk=load_money.pk).update(
                status='FAILED',
                failure_reason='Toucan pay-in is not enabled',
            )
            raise TransactionFailed(
                'Toucan pay-in is not enabled. Razorpay remains the pay-in provider.'
            )
        base = (os.getenv('PAYMENT_HUB_BASE_URL') or '').rstrip('/')
        key = os.getenv('PAYMENT_HUB_API_KEY') or ''
        secret = os.getenv('PAYMENT_HUB_HMAC_SECRET') or ''
    if not base or not key or not secret:
        LoadMoney.objects.filter(pk=load_money.pk).update(
            status='FAILED',
            failure_reason='Toucan hub credential is not configured',
        )
        raise TransactionFailed('Toucan hub credential is not configured.')

    body = {
        'application_order_id': load_money.transaction_id,
        'amount': str(load_money.amount),
        'currency': 'INR',
        'name': contact.name or '',
        'phone': contact.phone or '',
        'email': contact.email or '',
    }
    raw = json.dumps(body, separators=(',', ':'), sort_keys=True).encode('utf-8')
    timestamp = str(int(time.time()))
    signature = hmac.new(secret.encode('utf-8'), f'{timestamp}.'.encode('utf-8') + raw, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        f'{base}/api/v1/payments',
        data=raw,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}',
            'X-Hub-Timestamp': timestamp,
            'X-Hub-Signature': signature,
            'User-Agent': HUB_USER_AGENT,
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as exc:
        reason = _hub_failure_reason(exc)
        logger.warning('Toucan hub checkout failed: %s', reason)
        LoadMoney.objects.filter(pk=load_money.pk).update(
            status='FAILED',
            failure_reason=reason,
        )
        raise TransactionFailed(reason) from exc

    response['redirect_url'] = data.get('redirect_url') or ''
    response['invoice'] = data.get('invoice') or ''
    response['provider'] = 'toucan'
    if data.get('invoice'):
        LoadMoney.objects.filter(pk=load_money.pk).update(provider_order_id=data.get('invoice'))
    return response


def _hub_credentials(load_money):
    from apps.fund_management.services import _toucan_credentials_from_gateway

    gateway = getattr(load_money, 'payment_gateway', None)
    if gateway is not None:
        creds = _toucan_credentials_from_gateway(gateway)
        if creds is not None:
            return creds
    if (getattr(load_money, 'payment_method', '') or '').lower() != 'toucan':
        return None
    if not hub_gate_open():
        raise TransactionFailed('Toucan pay-in is not enabled.')
    base = (os.getenv('PAYMENT_HUB_BASE_URL') or '').rstrip('/')
    key = os.getenv('PAYMENT_HUB_API_KEY') or ''
    secret = os.getenv('PAYMENT_HUB_HMAC_SECRET') or ''
    if not base or not key or not secret:
        raise TransactionFailed('Toucan hub credential is not configured.')
    return base, key, secret


def check_toucan_payin(load_money):
    """Ask the hub to call Toucan checkStatus for this pay-in."""
    if (getattr(load_money, 'collection_rail', '') or '').lower() == 'qr':
        raise TransactionFailed('This pay-in is a manual QR transfer. Gateway status does not apply.')
    creds = _hub_credentials(load_money)
    if creds is None:
        raise TransactionFailed('This pay-in was not opened on Toucan.')
    base, key, secret = creds
    body = {'application_order_id': load_money.transaction_id}
    invoice = (load_money.provider_order_id or '').strip()
    if invoice:
        body['invoice'] = invoice
    raw = json.dumps(body, separators=(',', ':'), sort_keys=True).encode('utf-8')
    timestamp = str(int(time.time()))
    signature = hmac.new(secret.encode('utf-8'), f'{timestamp}.'.encode('utf-8') + raw, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        f'{base}/api/v1/payments/status-check',
        data=raw,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}',
            'X-Hub-Timestamp': timestamp,
            'X-Hub-Signature': signature,
            'User-Agent': HUB_USER_AGENT,
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as exc:
        reason = _hub_failure_reason(exc)
        logger.warning('Toucan hub status check failed: %s', reason)
        raise TransactionFailed(reason) from exc
    return data
