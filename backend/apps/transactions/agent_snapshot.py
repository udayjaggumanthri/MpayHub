"""Agent attribution snapshots for enterprise reporting."""
from __future__ import annotations

from typing import Any

from apps.authentication.models import User


def display_name_for_user(user: User) -> str:
    if not user:
        return ''
    name = ''
    try:
        prof = getattr(user, 'profile', None)
        if prof is not None:
            name = (getattr(prof, 'full_name', None) or '').strip()
    except Exception:
        name = ''
    if not name:
        name = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    if not name:
        name = (getattr(user, 'email', None) or '') or ''
    if not name:
        name = str(getattr(user, 'user_id', None) or user.pk)
    return name.strip()


def agent_row_from_user(user: User | None) -> dict[str, Any]:
    """Shape used in API `agent_details` on every report row."""
    if not user:
        return {
            'id': None,
            'name': '',
            'role': '',
            'mobile': '',
            'user_code': '',
        }
    return {
        'id': user.pk,
        'name': display_name_for_user(user),
        'role': getattr(user, 'role', '') or '',
        'mobile': getattr(user, 'phone', '') or '',
        'user_code': str(getattr(user, 'user_id', None) or ''),
    }


def transaction_agent_db_fields(user: User | None) -> dict[str, Any]:
    """Kwargs for Transaction.objects.create / update for denormalized agent columns."""
    if not user:
        return {
            'agent_user': None,
            'agent_role_at_time': '',
            'agent_user_code': '',
            'agent_name_snapshot': '',
        }
    return {
        'agent_user': user,
        'agent_role_at_time': getattr(user, 'role', '') or '',
        'agent_user_code': str(getattr(user, 'user_id', None) or ''),
        'agent_name_snapshot': display_name_for_user(user),
    }


def passbook_initiator_db_fields(user: User | None) -> dict[str, Any]:
    if not user:
        return {
            'initiator_user': None,
            'initiator_role_at_time': '',
            'initiator_user_code': '',
            'initiator_name_snapshot': '',
        }
    return {
        'initiator_user': user,
        'initiator_role_at_time': getattr(user, 'role', '') or '',
        'initiator_user_code': str(getattr(user, 'user_id', None) or ''),
        'initiator_name_snapshot': display_name_for_user(user),
    }


def card_last4_from_payment_meta(meta: dict | None) -> str:
    if not meta:
        return ''
    for key in ('last4', 'card_last4', 'card_last_four'):
        v = meta.get(key)
        if v is not None and str(v).strip():
            s = ''.join(c for c in str(v) if c.isdigit())[-4:]
            return s
    # Razorpay-style nested
    card = meta.get('card') or {}
    if isinstance(card, dict):
        v = card.get('last4') or card.get('last_four')
        if v:
            return ''.join(c for c in str(v) if c.isdigit())[-4:]
    return ''


def utr_or_bank_reference_from_payment_meta(meta: dict | None) -> str:
    """Best-effort bank / UTR style reference from provider meta (Razorpay etc.)."""
    if not meta:
        return ''
    for k in (
        'rrn',
        'bank_rrn',
        'bank_transaction_id',
        'arn',
        'acquirer_reference_number',
        'receipt',
    ):
        v = meta.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()[:191]
    acq = meta.get('acquirer_data')
    if isinstance(acq, dict):
        for k in ('auth_reference_number', 'rrn', 'transaction_id', 'bank_transaction_id'):
            v = acq.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()[:191]
    return ''
