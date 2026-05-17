"""
Normalize BBPS bill-payment rows for receipt / transaction-detail UIs.
"""
from __future__ import annotations

from apps.bbps.models import BbpsBillerMaster, BillPayment
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
        master = (
            BbpsBillerMaster.objects.filter(biller_id=biller_id, is_deleted=False)
            .only('biller_name')
            .first()
        )
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
        _pick_br(br, 'billNumber', 'bill_number', 'consumerNumber', 'customerRefNumber')
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

    biller_name = _biller_display_name(payment)

    return {
        'biller_name': biller_name,
        'customer_name': customer_name,
        'bill_date': bill_date,
        'bill_period': bill_period,
        'due_date': due_date,
        'bill_number': bill_number,
        'payment_mode': payment_mode,
        'init_channel': init_channel,
        'remitter_name': remitter,
    }
