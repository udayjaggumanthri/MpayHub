"""
Wallet summary presentation adapters.

Keeps personal balance building separate from Admin network-total display.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

from apps.wallets.portfolio import (
    NETWORK_WALLET_TYPES,
    network_wallet_user_counts,
    sum_network_wallet_balances,
)


def _money_str(value: Decimal | str | int | float | None) -> str:
    try:
        return f'{Decimal(str(value or 0)):.2f}'
    except Exception:
        return '0.00'


def present_wallet_summary_for_viewer(user, personal_summary: dict) -> dict:
    """
    Return wallet summary for the authenticated viewer.

    Non-Admin: personal balances unchanged.
    Admin: main/bbps balances replaced with live network totals (display-only).
    """
    summary = deepcopy(personal_summary or {})
    role = getattr(user, 'role', None) or ''
    if role != 'Admin':
        return summary

    totals = sum_network_wallet_balances(wallet_types=NETWORK_WALLET_TYPES)
    user_counts = network_wallet_user_counts(wallet_types=NETWORK_WALLET_TYPES)

    for wt in NETWORK_WALLET_TYPES:
        entry = summary.get(wt)
        if not isinstance(entry, dict):
            entry = {'balance': '0.00'}
        else:
            entry = dict(entry)
        entry['balance'] = _money_str(totals.get(wt, Decimal('0')))
        entry['source'] = 'network_total'
        entry['network_user_count'] = int(user_counts.get(wt, 0))
        summary[wt] = entry

    return summary
