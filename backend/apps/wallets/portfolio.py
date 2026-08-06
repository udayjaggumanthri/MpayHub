"""
Read-only network wallet portfolio for Admin display.

Sums non-Admin users' wallet balances. Never writes or creates wallet rows.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from apps.wallets.models import Wallet

NETWORK_WALLET_TYPES = ('main', 'bbps')
ADMIN_ROLE = 'Admin'


def sum_network_wallet_balances(
    *,
    wallet_types: Iterable[str] = NETWORK_WALLET_TYPES,
) -> dict[str, Decimal]:
    """
    Return {wallet_type: total_balance} for all users whose role is not Admin.

    Missing types are returned as Decimal('0').
    """
    types = tuple(dict.fromkeys(str(t).strip().lower() for t in wallet_types if t))
    if not types:
        return {}

    zeros = {t: Decimal('0') for t in types}
    rows = (
        Wallet.objects.filter(wallet_type__in=types)
        .exclude(user__role=ADMIN_ROLE)
        .values('wallet_type')
        .annotate(total=Coalesce(Sum('balance'), Decimal('0')))
    )
    for row in rows:
        wt = row['wallet_type']
        if wt in zeros:
            zeros[wt] = Decimal(str(row['total'] or 0))
    return zeros


def network_wallet_user_counts(
    *,
    wallet_types: Iterable[str] = NETWORK_WALLET_TYPES,
) -> dict[str, int]:
    """Distinct non-Admin users that have a wallet row per type."""
    types = tuple(dict.fromkeys(str(t).strip().lower() for t in wallet_types if t))
    if not types:
        return {}
    counts = {t: 0 for t in types}
    rows = (
        Wallet.objects.filter(wallet_type__in=types)
        .exclude(user__role=ADMIN_ROLE)
        .values('wallet_type')
        .annotate(n=Count('user_id', distinct=True))
    )
    for row in rows:
        wt = row['wallet_type']
        if wt in counts:
            counts[wt] = int(row['n'] or 0)
    return counts
