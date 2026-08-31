"""Enterprise pay-in receipt context for reports and print."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.urls import reverse

from apps.fund_management.models import LoadMoney
from apps.fund_management.payin_rail_labels import (
    payin_collection_method_label,
    payin_is_qr_rail,
    payin_qr_account_label,
    payin_rail_type_label,
)
from apps.fund_management.serializers import payin_payment_mode_display
from apps.users.identity import public_display_code


def _money_str(v) -> str:
    if v is None:
        return ''
    return str(Decimal(str(v)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def _qr_proof_receipt_url(request, lm: LoadMoney) -> str:
    if not payin_is_qr_rail(lm) or not lm.receipt_image:
        return ''
    try:
        path = reverse('fund_management:pay-in-qr-receipt', kwargs={'transaction_id': lm.transaction_id})
        if request:
            return request.build_absolute_uri(path)
        return path
    except Exception:
        return ''


def build_payin_receipt_context(lm: LoadMoney, request=None) -> dict[str, Any]:
    """Structured receipt payload for UI + print (BBPS-style)."""
    user = lm.user
    prof = getattr(user, 'profile', None) if user else None
    agent_name = ''
    if prof and getattr(prof, 'full_name', None):
        agent_name = prof.full_name
    elif user:
        agent_name = getattr(user, 'email', '') or ''
    agent_code = public_display_code(user) if user else ''

    pkg = lm.package
    package_name = ''
    if pkg:
        package_name = str(getattr(pkg, 'display_name', '') or getattr(pkg, 'code', '') or '').strip()

    status = (lm.status or 'PENDING').upper()
    payment_date = ''
    if getattr(lm, 'payment_date', None):
        payment_date = lm.payment_date.isoformat()

    return {
        'transaction_id': lm.transaction_id,
        'receipt_no': lm.transaction_id,
        'status': status,
        'collection_rail': (lm.collection_rail or 'gateway').strip().lower(),
        'rail_type_label': payin_rail_type_label(lm),
        'collection_method': payin_collection_method_label(lm),
        'payment_mode': payin_payment_mode_display(lm),
        'qr_account_name': payin_qr_account_label(lm),
        'utr': (lm.utr or lm.gateway_transaction_id or '').strip(),
        'gateway_reference': (lm.gateway_transaction_id or lm.provider_payment_id or '').strip(),
        'provider_order_id': (lm.provider_order_id or '').strip(),
        'provider_payment_id': (lm.provider_payment_id or '').strip(),
        'customer_name': (lm.customer_name or '').strip(),
        'customer_email': (lm.customer_email or '').strip(),
        'customer_phone': (lm.customer_phone or '').strip(),
        'agent_name': agent_name,
        'agent_code': agent_code,
        'package_name': package_name,
        'gross_amount': _money_str(lm.amount),
        'charges': _money_str(lm.charge),
        'net_credit': _money_str(lm.net_credit),
        'submitted_amount': _money_str(lm.submitted_amount) if lm.submitted_amount is not None else '',
        'payment_date': payment_date,
        'transaction_date': lm.created_at.isoformat() if lm.created_at else '',
        'reviewed_at': lm.reviewed_at.isoformat() if getattr(lm, 'reviewed_at', None) else '',
        'failure_reason': (lm.failure_reason or '').strip(),
        'proof_receipt_url': _qr_proof_receipt_url(request, lm),
        'has_proof_image': bool(payin_is_qr_rail(lm) and lm.receipt_image),
    }
