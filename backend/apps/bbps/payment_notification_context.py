"""
Context variables for BBPS payment SMS/email notifications.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from apps.bbps.models import BbpsServiceCategory
from apps.bbps.receipt_context import (
    _pick_customer_details,
    _pick_input_param,
    build_bill_payment_receipt_context,
)
from apps.bbps.services import normalize_category_code, to_title_case

if TYPE_CHECKING:
    from apps.authentication.models import User
    from apps.bbps.models import BbpsPaymentAttempt

_STATUS_DISPLAY = {
    'SUCCESS': 'Success',
    'AWAITED': 'Pending',
    'FAILED': 'Failed',
}

_GENERIC_CONSUMER_PATTERNS = (
    r'customer.?id',
    r'customer.?number',
    r'consumer.?number',
    r'consumer.?id',
    r'subscriber',
    r'mobile',
    r'msisdn',
    r'account.?id',
)


def resolve_user_display_name(user: 'User') -> str:
    profile = getattr(user, 'profile', None)
    if profile is not None:
        fn = f'{profile.first_name or ""} {profile.last_name or ""}'.strip()
        if fn:
            return fn
        business = str(getattr(profile, 'business_name', '') or '').strip()
        if business:
            return business
    full = (user.get_full_name() or '').strip()
    if full:
        return full
    phone = str(getattr(user, 'phone', '') or '').strip()
    return phone or 'Customer'


def resolve_service_label(bill_type: str) -> str:
    slug = normalize_category_code(bill_type)
    if not slug:
        return 'Bill Payment'
    row = (
        BbpsServiceCategory.objects.filter(is_deleted=False, is_active=True, code=slug)
        .only('name')
        .first()
    )
    if row and str(row.name or '').strip():
        return str(row.name).strip()
    return to_title_case(slug)


def _is_fastag_category(bill_type: str) -> bool:
    raw = str(bill_type or '').lower()
    norm = normalize_category_code(bill_type)
    return norm == 'fastag' or norm == 'fast-tag' or 'fastag' in raw


def _is_credit_card_category(bill_type: str) -> bool:
    raw = str(bill_type or '').lower()
    return 'credit' in raw and 'card' in raw


def _is_mobile_category(bill_type: str) -> bool:
    return 'mobile' in str(bill_type or '').lower()


def _pick_by_patterns(payload: dict, patterns: tuple[str, ...]) -> str:
    val = _pick_customer_details(payload, *patterns)
    if val:
        return val
    return _pick_input_param(payload, *patterns)


def _derive_generic_consumer_id(payload: dict, bill_number: str) -> str:
    if bill_number:
        return bill_number
    for pattern in _GENERIC_CONSUMER_PATTERNS:
        val = _pick_by_patterns(payload, (pattern,))
        if val:
            return val
    for key in ('customer_id', 'customer_number', 'mobile', 'card_last4'):
        val = str(payload.get(key) or '').strip()
        if val:
            return val
    return ''


def resolve_consumer_id(attempt: 'BbpsPaymentAttempt') -> str:
    payload = attempt.request_payload if isinstance(attempt.request_payload, dict) else {}
    payment = attempt.bill_payment
    bill_type = str(getattr(payment, 'bill_type', '') or payload.get('bill_type') or '').strip()

    bill_number = ''
    if payment:
        ctx = build_bill_payment_receipt_context(payment)
        bill_number = str(ctx.get('bill_number') or '').strip()

    if _is_fastag_category(bill_type):
        vehicle = _pick_by_patterns(
            payload,
            (r'vehicle', r'registration', r'\breg\b', r'\bvrn\b', r'\brc\b', r'veh.*no', r'car.*no'),
        )
        if not vehicle:
            vehicle = str(payload.get('vehicle_number') or payload.get('vehicle_no') or '').strip()
        if vehicle:
            return vehicle
        if bill_number:
            return bill_number

    if _is_credit_card_category(bill_type):
        last4 = _pick_by_patterns(payload, (r'card.*last.?4', r'last.?4', r'card.*digit'))
        if not last4:
            last4 = str(payload.get('card_last4') or payload.get('cardLast4') or '').strip()
        if last4:
            return last4

    if _is_mobile_category(bill_type):
        mobile = _pick_by_patterns(payload, (r'mobile', r'phone'))
        if not mobile:
            mobile = str(payload.get('mobile') or payload.get('mobileNumber') or '').strip()
        if mobile:
            return mobile

    return _derive_generic_consumer_id(payload, bill_number)


def resolve_b_connect_txn_id(attempt: 'BbpsPaymentAttempt') -> str:
    payment = attempt.bill_payment
    for val in (
        attempt.txn_ref_id,
        attempt.approval_ref_number,
        attempt.request_id,
        getattr(payment, 'request_id', None) if payment else None,
    ):
        s = str(val or '').strip()
        if s:
            return s
    return ''


def status_display(status: str) -> str:
    return _STATUS_DISPLAY.get((status or '').upper(), str(status or '').strip() or 'Unknown')


def _amount_str(attempt: 'BbpsPaymentAttempt') -> str:
    paise = int(attempt.amount_paise or 0)
    return str((Decimal(paise) / Decimal('100')).quantize(Decimal('0.01')))


def _biller_name(attempt: 'BbpsPaymentAttempt') -> str:
    bill_payment = attempt.bill_payment
    if bill_payment and getattr(bill_payment, 'biller', None):
        return str(bill_payment.biller)
    payload = attempt.request_payload if isinstance(attempt.request_payload, dict) else {}
    return str(payload.get('biller') or payload.get('biller_name') or attempt.biller_id or 'BBPS')


def build_payment_notification_context(attempt: 'BbpsPaymentAttempt', status: str) -> dict:
    """Template context for BBPS payment SMS/email (new + legacy keys)."""
    status_upper = (status or '').upper()
    bill_type = ''
    if attempt.bill_payment:
        bill_type = str(attempt.bill_payment.bill_type or '')

    b_connect_txn_id = resolve_b_connect_txn_id(attempt)
    consumer_id = resolve_consumer_id(attempt) or 'NA'
    receipt_no = b_connect_txn_id or (attempt.service_id or '') or 'NA'
    context = {
        'name': resolve_user_display_name(attempt.user),
        'service': resolve_service_label(bill_type),
        'consumer_id': consumer_id,
        'b_connect_txn_id': b_connect_txn_id,
        'status': status_display(status_upper),
        'biller': _biller_name(attempt),
        'amount': _amount_str(attempt),
        'service_id': attempt.service_id or '',
        'receipt_no': receipt_no,
    }
    if status_upper in ('SUCCESS', 'AWAITED'):
        context['txn_ref'] = b_connect_txn_id or receipt_no
    if status_upper == 'FAILED':
        context['reason'] = (attempt.last_error_message or '')[:200]
    return context
