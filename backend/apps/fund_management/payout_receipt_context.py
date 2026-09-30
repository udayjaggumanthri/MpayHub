"""Enterprise payout receipt context for reports and print."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.fund_management.models import Payout
from apps.users.identity import public_display_code


def _money_str(v) -> str:
    if v is None:
        return ''
    return str(Decimal(str(v)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def build_payout_receipt_context(payout: Payout, request=None) -> dict[str, Any]:
    """
    Structured receipt payload for UI + print (pay-in / BBPS style).
    Account numbers are full (unmasked) for the receipt surface.
    """
    del request  # reserved for absolute URLs if needed later
    user = payout.user
    bank = payout.bank_account

    agent_name = ''
    agent_mobile = ''
    agent_code = ''
    if user:
        try:
            prof = getattr(user, 'profile', None)
            if prof and getattr(prof, 'full_name', None):
                agent_name = str(prof.full_name).strip()
        except Exception:
            agent_name = ''
        if not agent_name:
            agent_name = (getattr(user, 'email', '') or '').strip()
        agent_mobile = (getattr(user, 'phone', '') or '').strip()
        agent_code = public_display_code(user) or ''

    bank_name = ''
    account_number = ''
    ifsc = ''
    account_holder_name = ''
    beneficiary_mobile = ''
    if bank:
        bank_name = (getattr(bank, 'bank_name', '') or '').strip()
        account_number = (getattr(bank, 'account_number', '') or '').strip()
        ifsc = (getattr(bank, 'ifsc', '') or '').strip().upper()
        account_holder_name = (
            (getattr(bank, 'beneficiary_name', None) or '')
            or (getattr(bank, 'account_holder_name', None) or '')
            or ''
        ).strip()
        beneficiary_mobile = (getattr(bank, 'mobile_number', '') or '').strip()

    status = (payout.status or 'PENDING').upper()
    bank_ref = (
        (getattr(payout, 'rrn', None) or '')
        or (getattr(payout, 'gateway_transaction_id', None) or '')
        or (getattr(payout, 'provider_txn_id', None) or '')
        or ''
    ).strip()

    return {
        'transaction_id': payout.transaction_id or '',
        'receipt_no': payout.transaction_id or '',
        'status': status,
        'transfer_mode': (payout.transfer_mode or '').strip().upper(),
        'sender_info': beneficiary_mobile,
        'sender_name': account_holder_name,
        'account_number': account_number,
        'bank_name': bank_name,
        'ifsc': ifsc,
        'account_holder_name': account_holder_name,
        'beneficiary_mobile': beneficiary_mobile,
        'amount': _money_str(payout.amount),
        'charge': _money_str(payout.charge),
        'platform_fee': _money_str(getattr(payout, 'platform_fee', None) or Decimal('0')),
        'total_debit': _money_str(payout.total_deducted),
        'bank_ref_no': bank_ref,
        'rrn': (getattr(payout, 'rrn', None) or '').strip(),
        'provider_txn_id': (getattr(payout, 'provider_txn_id', None) or '').strip(),
        'provider_code': (getattr(payout, 'provider_code', None) or '').strip(),
        'provider_status_code': (getattr(payout, 'provider_status_code', None) or '').strip(),
        'transaction_date': payout.created_at.isoformat() if payout.created_at else '',
        'callback_received_at': (
            payout.callback_received_at.isoformat()
            if getattr(payout, 'callback_received_at', None)
            else ''
        ),
        'agent_name': agent_name,
        'agent_code': agent_code,
        'agent_mobile': agent_mobile,
        'purpose_code': (getattr(payout, 'purpose_code', None) or '').strip(),
        'beneficiary_location': (getattr(payout, 'beneficiary_location', None) or '').strip(),
    }
