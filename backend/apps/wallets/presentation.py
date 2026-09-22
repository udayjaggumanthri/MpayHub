"""
Wallet summary presentation adapters.

Keeps personal balance building separate from Admin Distributed Balance display.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

from apps.core.roles import is_platform_operator
from apps.wallets.portfolio import distributed_balance_snapshot


def _money_str(value: Decimal | str | int | float | None) -> str:
    try:
        return f'{Decimal(str(value or 0)):.2f}'
    except Exception:
        return '0.00'


def present_wallet_summary_for_viewer(user, personal_summary: dict) -> dict:
    """
    Return wallet summary for the authenticated viewer.

    Non-Admin: personal main balance unchanged.
    Admin / Super Admin: Main is the shared platform treasury (same number on
    every operator login); attach ``distributed`` as the live network total.
    Never overwrites the treasury main with network sums.
    """
    summary = deepcopy(personal_summary or {})
    role = getattr(user, 'role', None) or ''
    if not is_platform_operator(role):
        return summary

    snap = distributed_balance_snapshot()
    summary['distributed'] = {
        'balance': _money_str(snap['balance']),
        'source': 'network_total',
        'network_user_count': snap['network_user_count'],
        'wallet_type': 'distributed',
    }
    return summary
