"""
Normalize BBPS bill-payment rows for receipt / transaction-detail UIs.
"""
from __future__ import annotations

import re

from apps.bbps.catalog.env import get_biller_master
from apps.bbps.models import BillPayment
from apps.integrations.bbps_client import (
    _scalar_field,
    extract_biller_response_dict,
    resolve_remitter_display_name,
)


def _payload_from_payment(payment: BillPayment) -> dict:
    attempt = (
        payment.attempts.filter(is_deleted=False).order_by('-created_at').first()
    )
    payload = getattr(attempt, 'request_payload', None) if attempt else None
    return payload if isinstance(payload, dict) else {}


def _latest_attempt(payment: BillPayment):
    return payment.attempts.filter(is_deleted=False).order_by('-created_at').first()


def _biller_display_name(payment: BillPayment) -> str:
    biller_id = str(payment.biller_id or '').strip()
    if biller_id:
        master = get_biller_master(biller_id)
        if master and str(master.biller_name or '').strip():
            return str(master.biller_name).strip()
    stored = str(payment.biller or '').strip()
    if stored and stored != biller_id:
        return stored
    return ''


def _extract_biller_response(payload: dict) -> dict:
    if not payload:
        return {}
    nested = payload.get('biller_response')
    if isinstance(nested, dict) and nested:
        return extract_biller_response_dict(nested) or nested
    return extract_biller_response_dict(payload) or {}


def _pick_br(br: dict, *keys: str) -> str:
    for key in keys:
        val = _scalar_field(br, key)
        if val:
            return val
    return ''


def _pick_customer_details(payload: dict, *patterns) -> str:
    details = payload.get('customer_details')
    if not isinstance(details, dict):
        return ''
    import re

    for label, value in details.items():
        key = str(label or '').strip().lower()
        val = str(value or '').strip()
        if not key or not val:
            continue
        if any(re.search(p, key, re.I) for p in patterns):
            return val
    return ''


def _pick_input_param(payload: dict, *patterns) -> str:
    import re

    rows = payload.get('input_params')
    if not isinstance(rows, list):
        return ''
    for item in rows:
        if not isinstance(item, dict):
            continue
        key = str(item.get('paramName') or item.get('param_name') or '').strip().lower()
        val = str(item.get('paramValue') or item.get('param_value') or '').strip()
        if not key or not val:
            continue
        if any(re.search(p, key, re.I) for p in patterns):
            return val
    return ''


def _humanize_param_label(raw: str) -> str:
    s = str(raw or '').strip()
    if not s:
        return 'Customer ID'
    if ' ' in s:
        return s
    # CustomerId / ServiceNumber → Customer ID / Service Number
    spaced = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)
    spaced = spaced.replace('_', ' ').replace('-', ' ')
    parts = []
    for part in spaced.split():
        if part.lower() == 'id':
            parts.append('ID')
        elif len(part) <= 2 and part.isalpha():
            parts.append(part.upper())
        else:
            parts.append(part[:1].upper() + part[1:])
    return ' '.join(parts)


def _score_identity_key(key: str) -> int:
    import re

    k = str(key or '').strip()
    if not k:
        return 0
    rules = (
        (r'service.?number|service.?no|\bservice.?id\b', 100),
        (r'consumer.?number|consumer.?no|consumer.?id|ca.?number|connection', 96),
        (r'customer.?id|customer.?number|customer.?no|account.?id|account.?number', 92),
        (r'vehicle|registration|\bvrn\b|\brc\b', 92),
        (r'card.?last|last.?4|last.?four|card.?digit', 92),
        (r'subscriber|policy.?number|loan.?account|meter', 88),
        (r'mobile|phone|msisdn', 72),
        (r'\bnumber\b|\bid\b|\baccount\b', 40),
    )
    best = 0
    for pattern, score in rules:
        if re.search(pattern, k, re.I):
            best = max(best, score)
    return best


def _pick_receipt_identity(payload: dict) -> tuple[str, str]:
    """Return (label, value) for the consumer account from MDM input params."""
    import re

    skip = re.compile(
        r'^(plan.?id|amount|payment.?amount|bill.?amount|circle|operator|otp|mpin|email)$',
        re.I,
    )
    candidates: list[tuple[int, str, str]] = []
    rows = payload.get('input_params') if isinstance(payload.get('input_params'), list) else []
    for idx, item in enumerate(rows):
        if not isinstance(item, dict):
            continue
        label = str(item.get('paramName') or item.get('param_name') or '').strip()
        value = str(item.get('paramValue') or item.get('param_value') or '').strip()
        if not label or not value or value.upper() in ('N/A', 'NA', '-'):
            continue
        if skip.search(label):
            continue
        score = _score_identity_key(label) or 15
        candidates.append((score - idx * 0.01, label, value))
    details = payload.get('customer_details') if isinstance(payload.get('customer_details'), dict) else {}
    for idx, (label, value) in enumerate(details.items()):
        label_s = str(label or '').strip()
        value_s = str(value or '').strip()
        if not label_s or not value_s or value_s.upper() in ('N/A', 'NA', '-'):
            continue
        if skip.search(label_s):
            continue
        score = _score_identity_key(label_s) or 15
        candidates.append((score - idx * 0.01, label_s, value_s))
    if not candidates:
        return '', ''
    candidates.sort(key=lambda row: row[0], reverse=True)
    _, label, value = candidates[0]
    return _humanize_param_label(label), value


def build_bill_payment_receipt_context(payment: BillPayment) -> dict:
    """Receipt-friendly fields; varies by category (fetch bill vs quick pay)."""
    payload = _payload_from_payment(payment)
    attempt = _latest_attempt(payment)
    br = _extract_biller_response(payload)

    payment_mode = ''
    init_channel = ''
    if attempt:
        payment_mode = str(attempt.payment_mode or '').strip()
        init_channel = str(attempt.payment_channel or '').strip()
    if not payment_mode:
        payment_mode = str(payload.get('payment_mode') or '').strip()
    if not init_channel:
        init_channel = str(payload.get('init_channel') or '').strip()
    if not init_channel:
        adi = payload.get('agent_device_info')
        if isinstance(adi, dict):
            init_channel = str(adi.get('initChannel') or adi.get('init_channel') or '').strip()

    customer_name = (
        resolve_remitter_display_name(payload)
        or str(payload.get('customer_name') or '').strip()
        or _pick_br(br, 'customerName', 'ConsumerName', 'accountHolderName', 'name')
        or _pick_customer_details(payload, r'customer.?name', r'^name$', r'consumer.?name', r'account.?holder')
    )
    remitter = str(payload.get('remitter_name') or '').strip()
    if not customer_name and remitter:
        customer_name = remitter

    bill_date = _pick_br(br, 'billDate', 'bill_date') or _pick_customer_details(
        payload, r'bill.?date'
    )
    bill_period = _pick_br(br, 'billPeriod', 'bill_period') or _pick_customer_details(
        payload, r'bill.?period'
    )
    due_date = _pick_br(br, 'dueDate', 'due_date') or _pick_customer_details(payload, r'due.?date')
    bill_number = (
        _pick_br(
            br,
            'billNumber',
            'bill_number',
            'respBillNumber',
            'RespBillNumber',
            'consumerNumber',
            'customerRefNumber',
        )
        or _pick_customer_details(payload, r'bill.?number', r'consumer.?number', r'registration', r'vehicle')
        or _pick_input_param(
            payload,
            r'bill.?number',
            r'vehicle',
            r'registration',
            r'consumer.?number',
            r'customer.?number',
            r'mobile',
        )
    )
    # Pay response often stores bill number only as respBillNumber on the attempt payload.
    if not bill_number and attempt is not None:
        resp = getattr(attempt, 'response_payload', None)
        if isinstance(resp, dict):
            bill_number = (
                _pick_br(resp, 'respBillNumber', 'RespBillNumber', 'billNumber', 'bill_number')
                or _pick_br(
                    resp.get('ExtBillPayResponse') if isinstance(resp.get('ExtBillPayResponse'), dict) else {},
                    'respBillNumber',
                    'RespBillNumber',
                    'billNumber',
                )
            )

    identity_label, identity_value = _pick_receipt_identity(payload)
    biller_name = _biller_display_name(payment)

    return {
        'biller_name': biller_name,
        'customer_name': customer_name,
        'bill_date': bill_date,
        'bill_period': bill_period,
        'due_date': due_date,
        'bill_number': bill_number,
        'identity_label': identity_label,
        'identity_value': identity_value,
        'payment_mode': payment_mode,
        'init_channel': init_channel,
        'remitter_name': remitter,
    }
