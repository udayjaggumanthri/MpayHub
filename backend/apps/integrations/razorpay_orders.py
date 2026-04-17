"""Razorpay Orders API (server-side)."""
import base64
import hashlib
import hmac
import json
import logging
import re
import time

from decimal import Decimal, ROUND_HALF_UP

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _strip_cred(value):
    if value is None:
        return ''
    return str(value).strip()


# Razorpay Key ID format (test and live)
_RZP_KEY_ID_RE = re.compile(r'^rzp_(test|live)_[A-Za-z0-9]+$')


def is_razorpay_like_provider_code(provider_code: str) -> bool:
    """
    Detect Razorpay entries even if operator_code has a typo (e.g. 'razopay') or extra suffix.
    Used so Test Connection runs real auth instead of a blind HTTP GET to base_url.
    """
    c = (provider_code or '').strip().lower()
    if 'razorpay' in c:
        return True
    if c == 'razopay':
        return True
    if c.startswith('razo') and c.endswith('pay') and len(c) <= 12:
        return True
    return False


def _normalize_secret_keys(secrets: dict) -> dict:
    """Lowercase keys, spaces/dashes → underscores (UI often uses 'Test API Key', etc.)."""
    out = {}
    for raw_k, v in (secrets or {}).items():
        k = str(raw_k).strip().lower().replace('-', '_')
        k = '_'.join(part for part in k.split() if part)
        while '__' in k:
            k = k.replace('__', '_')
        out[k] = v
    return out


def extract_razorpay_key_pair_from_secrets(secrets: dict):
    """
    Read Razorpay key id + secret from an API Master secrets dict.
    Accepts common label variants and, if needed, infers id/secret from values (rzp_test_/rzp_live_).
    Also fixes a common UI mistake: putting the Key ID string in the "Key" column instead of key_id.
    Returns (key_id, key_secret) only if both are resolved (avoids mixing with env).
    """
    if not secrets:
        return None, None

    # Mislabeled rows: JSON key is literally rzp_test_… / rzp_live_… (value = secret, or secret in another row).
    for raw_k, v in secrets.items():
        k_candidate = str(raw_k).strip()
        if _RZP_KEY_ID_RE.match(k_candidate):
            sec = _strip_cred(v)
            if sec:
                return k_candidate, sec
    for raw_k, v in secrets.items():
        k_candidate = str(raw_k).strip()
        if not _RZP_KEY_ID_RE.match(k_candidate):
            continue
        if _strip_cred(v):
            continue
        others = [
            _strip_cred(val)
            for key, val in secrets.items()
            if str(key).strip() != k_candidate and _strip_cred(val)
        ]
        for cand in sorted(others, key=len, reverse=True):
            if len(cand) >= 12 and not cand.startswith('rzp_'):
                return k_candidate, cand

    n = _normalize_secret_keys(secrets)

    kid = _strip_cred(
        n.get('key_id')
        or n.get('api_key')
        or n.get('razorpay_key_id')
        or n.get('test_api_key')
        or n.get('public_key')
        or n.get('client_id')
    )
    ksec = _strip_cred(
        n.get('key_secret')
        or n.get('api_secret')
        or n.get('razorpay_key_secret')
        or n.get('test_key_secret')
        or n.get('test_api_secret')
        or n.get('secret')
        or n.get('client_secret')
        or n.get('private_key')
    )
    if kid and ksec:
        return kid, ksec

    # Values only: e.g. keys labeled "Key 1" / "Key 2" from dashboard copy-paste
    vals = [_strip_cred(v) for v in secrets.values() if _strip_cred(v)]
    inferred_id = next((v for v in vals if _RZP_KEY_ID_RE.match(v)), '')
    others = [v for v in vals if v != inferred_id]
    inferred_sec = ''
    for v in sorted(others, key=len, reverse=True):
        if len(v) >= 12 and not v.startswith('rzp_'):
            inferred_sec = v
            break
    if inferred_id and inferred_sec:
        return inferred_id, inferred_sec
    return None, None


def resolve_razorpay_credentials(key_id=None, key_secret=None):
    """
    Use explicit key pair only when BOTH are non-empty; otherwise use env vars for BOTH.
    Per-field fallback (id from DB + secret from .env) causes Razorpay 401 Authentication failed.
    """
    env_id = _strip_cred(getattr(settings, 'RAZORPAY_KEY_ID', ''))
    env_sec = _strip_cred(getattr(settings, 'RAZORPAY_KEY_SECRET', ''))
    kid = _strip_cred(key_id)
    ksec = _strip_cred(key_secret)
    if kid and ksec:
        return kid, ksec
    return env_id, env_sec


def razorpay_is_configured(key_id=None, key_secret=None):
    kid, ksec = resolve_razorpay_credentials(key_id, key_secret)
    return bool(kid and ksec)


def verify_razorpay_basic_auth(key_id: str, key_secret: str, *, timeout: int = 10):
    """
    Call Razorpay list-orders with count=1 to validate key_id:key_secret.
    Returns (success: bool, status_code: int, detail: str).
    """
    kid, ksec = resolve_razorpay_credentials(key_id, key_secret)
    if not kid or not ksec:
        return False, 0, 'missing_credentials'
    auth = base64.b64encode(f'{kid}:{ksec}'.encode()).decode()
    try:
        r = requests.get(
            'https://api.razorpay.com/v1/orders',
            params={'count': 1},
            headers={'Authorization': f'Basic {auth}'},
            timeout=timeout,
        )
        if r.status_code == 200:
            return True, 200, 'ok'
        try:
            data = r.json()
            msg = data.get('error', {}).get('description', r.text[:200])
        except (ValueError, TypeError):
            msg = (r.text or '')[:200]
        return False, r.status_code, msg
    except requests.RequestException as e:
        logger.warning('Razorpay auth check request error: %s', e)
        return False, 0, str(e)


def create_order(*, amount_inr, receipt, notes=None, key_id=None, key_secret=None):
    """
    Create a Razorpay order. amount_inr is in INR (rupees), not paise.
    Returns (data dict or None, error_code str).
    """
    key_id, key_secret = resolve_razorpay_credentials(key_id, key_secret)
    if not razorpay_is_configured(key_id=key_id, key_secret=key_secret):
        return None, 'not_configured'

    auth = base64.b64encode(f'{key_id}:{key_secret}'.encode()).decode()
    d = amount_inr if isinstance(amount_inr, Decimal) else Decimal(str(amount_inr))
    paise = int((d * 100).to_integral_value(rounding=ROUND_HALF_UP))

    payload = {
        'amount': paise,
        'currency': 'INR',
        'receipt': receipt[:40],
        'notes': dict(notes or {}),
    }
    try:
        r = requests.post(
            'https://api.razorpay.com/v1/orders',
            headers={
                'Authorization': f'Basic {auth}',
                'Content-Type': 'application/json',
            },
            data=json.dumps(payload),
            timeout=45,
        )
        data = r.json()
        if r.status_code >= 400:
            logger.warning('Razorpay order failed: %s %s', r.status_code, data)
            return None, data.get('error', {}).get('description', 'order_failed')
        return data, None
    except requests.RequestException as e:
        logger.exception('Razorpay order request error')
        return None, str(e)


def verify_razorpay_checkout_signature(
    order_id: str, payment_id: str, signature: str, *, key_secret: str
) -> bool:
    """
    Validate signature returned by Razorpay Checkout (handler response).
    See: https://razorpay.com/docs/payments/server-integration/python/payment-verification/
    """
    if not order_id or not payment_id or not signature or not key_secret:
        return False
    body = f'{order_id}|{payment_id}'
    expected = hmac.new(
        str(key_secret).encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, str(signature).strip())


def capture_razorpay_payment(
    payment_id: str, *, amount_paise: int, currency: str = 'INR', key_id: str, key_secret: str
):
    """
    POST /v1/payments/{id}/capture — for manual-capture accounts or when checkout returns before auto-capture.
    amount_paise: full payment amount in paise (from payment entity).
    Returns (data dict or None, error str or None).
    """
    kid, ksec = resolve_razorpay_credentials(key_id, key_secret)
    if not kid or not ksec:
        return None, 'not_configured'
    auth = base64.b64encode(f'{kid}:{ksec}'.encode()).decode()
    try:
        r = requests.post(
            f'https://api.razorpay.com/v1/payments/{payment_id}/capture',
            headers={
                'Authorization': f'Basic {auth}',
                'Content-Type': 'application/json',
            },
            data=json.dumps({'amount': int(amount_paise), 'currency': currency}),
            timeout=30,
        )
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code >= 400:
            msg = data.get('error', {}).get('description', 'capture_failed') if isinstance(data, dict) else 'capture_failed'
            return None, msg
        return data if isinstance(data, dict) else None, None
    except requests.RequestException as e:
        logger.warning('Razorpay capture request error: %s', e)
        return None, str(e)


def fetch_razorpay_payment(payment_id: str, *, key_id: str, key_secret: str):
    """
    GET /v1/payments/{id} — confirm status (e.g. captured) after checkout.
    Returns (data dict or None, error str or None).
    """
    kid, ksec = resolve_razorpay_credentials(key_id, key_secret)
    if not kid or not ksec:
        return None, 'not_configured'
    auth = base64.b64encode(f'{kid}:{ksec}'.encode()).decode()
    try:
        r = requests.get(
            f'https://api.razorpay.com/v1/payments/{payment_id}',
            headers={'Authorization': f'Basic {auth}'},
            timeout=30,
        )
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code >= 400:
            msg = data.get('error', {}).get('description', 'fetch_failed') if isinstance(data, dict) else 'fetch_failed'
            return None, msg
        return data if isinstance(data, dict) else None, None
    except requests.RequestException as e:
        logger.warning('Razorpay payment fetch error: %s', e)
        return None, str(e)


def fetch_razorpay_payment_until_captured(
    payment_id: str,
    *,
    key_id: str,
    key_secret: str,
    max_attempts: int = 12,
    delay_sec: float = 0.45,
):
    """
    Checkout success handler often runs before Razorpay marks the payment ``captured``.
    Poll briefly, then optionally call capture (manual-capture mode / slow auto-capture).

    Returns (pay dict or None, error str or None).
    """
    payment_id = str(payment_id).strip()
    last_pay = None
    last_err = None
    for attempt in range(max(1, max_attempts)):
        pay, err = fetch_razorpay_payment(payment_id, key_id=key_id, key_secret=key_secret)
        last_pay, last_err = pay, err
        if err:
            if attempt == 0:
                return None, err
            break
        status = str((pay or {}).get('status') or '').lower()
        if status == 'captured':
            return pay, None
        if status in ('failed', 'refunded'):
            return None, f'payment_{status}'
        if attempt < max_attempts - 1:
            time.sleep(delay_sec)

    status = str((last_pay or {}).get('status') or '').lower()
    if status == 'authorized' and last_pay:
        amt = (last_pay or {}).get('amount')
        try:
            amount_paise = int(amt) if amt is not None else 0
        except (TypeError, ValueError):
            amount_paise = 0
        if amount_paise > 0:
            cap, cap_err = capture_razorpay_payment(
                payment_id,
                amount_paise=amount_paise,
                currency=str((last_pay or {}).get('currency') or 'INR'),
                key_id=key_id,
                key_secret=key_secret,
            )
            if not cap_err and isinstance(cap, dict) and str(cap.get('status') or '').lower() == 'captured':
                return cap, None
            if cap_err:
                logger.info(
                    'Razorpay capture after authorized skipped/failed payment=%s err=%s',
                    payment_id,
                    cap_err,
                )
        pay2, err2 = fetch_razorpay_payment(payment_id, key_id=key_id, key_secret=key_secret)
        if not err2 and pay2 and str(pay2.get('status') or '').lower() == 'captured':
            return pay2, None

    return last_pay, (
        last_err
        or f'Payment not captured yet (status={status or "unknown"}). '
        'If money was debited, wait a minute or ensure the Razorpay webhook is configured.'
    )


def verify_webhook_signature(body_bytes: bytes, signature_header: str) -> bool:
    """
    Razorpay signs webhooks with the secret from Dashboard → Webhooks (not always the API key secret).
    Set RAZORPAY_WEBHOOK_SECRET to that value; RAZORPAY_KEY_SECRET is only a fallback and may fail verification.
    """
    secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '') or getattr(settings, 'RAZORPAY_KEY_SECRET', '')
    if not secret or not signature_header:
        return False
    expected = hmac.new(
        secret.encode(),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def meta_from_razorpay_payment_entity(pay: dict) -> dict:
    """
    Normalize Razorpay payment entity fields we persist on LoadMoney.payment_meta
    (card last4, wallet/upi hints, acquirer_data for UTR, payer email/contact).
    """
    if not isinstance(pay, dict):
        return {}
    meta: dict = {}
    method = str(pay.get('method') or '').strip().lower()
    if method == 'card' and isinstance(pay.get('card'), dict):
        c = pay['card']
        if c.get('type'):
            meta['card_type'] = str(c.get('type')).lower()
        if c.get('network'):
            meta['network'] = str(c.get('network'))
        if c.get('last4'):
            meta['last4'] = ''.join(x for x in str(c.get('last4')) if x.isdigit())[-4:]
    if method == 'wallet' and isinstance(pay.get('wallet'), dict):
        w = pay['wallet']
        if w.get('type'):
            meta['wallet_type'] = str(w.get('type')).lower()
    if pay.get('vpa'):
        meta['vpa'] = str(pay.get('vpa')).strip()
    if pay.get('email'):
        meta['rzp_email'] = str(pay.get('email')).strip()
    if pay.get('contact'):
        meta['rzp_contact'] = str(pay.get('contact')).strip()
    if pay.get('description'):
        meta['rzp_description'] = str(pay.get('description')).strip()
    if pay.get('acquirer_data'):
        meta['acquirer_data'] = pay.get('acquirer_data')
    if isinstance(pay.get('bank'), dict):
        meta['bank'] = pay.get('bank')
    return meta


def parse_payment_captured_event(body_json: dict):
    """
    Extract order_id, payment_id, method, and small meta from payment.captured payload.
    Returns (order_id, payment_id, method, meta_dict). meta_dict may include card_type, network.
    """
    try:
        payload = body_json.get('payload', {})
        pay = payload.get('payment', {}).get('entity', {}) or {}
        order_id = pay.get('order_id')
        payment_id = pay.get('id')
        method = pay.get('method')
        meta = meta_from_razorpay_payment_entity(pay)
        return order_id, payment_id, method, meta
    except (TypeError, AttributeError):
        return None, None, None, {}


def parse_order_paid_event(body_json: dict):
    """
    order.paid — order fully paid; payload often includes both order and payment entities.
    Returns (order_id, payment_id, method, meta_dict) same shape as parse_payment_captured_event.
    """
    try:
        payload = body_json.get('payload', {})
        order_ent = (payload.get('order') or {}).get('entity', {}) or {}
        pay = (payload.get('payment') or {}).get('entity', {}) or {}
        order_id = order_ent.get('id') or pay.get('order_id')
        payment_id = pay.get('id')
        if not payment_id:
            return order_id, None, None, {}
        method = pay.get('method')
        meta = meta_from_razorpay_payment_entity(pay)
        return order_id, payment_id, method, meta
    except (TypeError, AttributeError):
        return None, None, None, {}
