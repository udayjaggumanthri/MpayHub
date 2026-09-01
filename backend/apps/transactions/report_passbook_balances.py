"""
Batch passbook opening/closing lookup for enterprise report rows.

Each report type maps to the transaction owner's wallet passbook line at settlement.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from apps.transactions.models import PassbookEntry


def _money_str(v: Decimal | None) -> str:
    if v is None:
        return ''
    return str(Decimal(str(v)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))

BalanceKey = tuple[str, int]  # (service_id, user_id)


@dataclass(frozen=True)
class BalancePair:
    opening: str
    closing: str

    @classmethod
    def empty(cls) -> BalancePair:
        return cls(opening='', closing='')

    @classmethod
    def from_entry(cls, entry: PassbookEntry | None) -> BalancePair:
        if entry is None:
            return cls.empty()
        return cls(opening=_money_str(entry.opening_balance), closing=_money_str(entry.closing_balance))


def passbook_balance_map(
    keys: list[BalanceKey],
    *,
    wallet_type: str,
    services: list[str] | None = None,
    credit_only: bool = False,
    debit_only: bool = False,
) -> dict[BalanceKey, BalancePair]:
    """
    Latest passbook row per (service_id, user_id) matching filters.
    """
    if not keys:
        return {}
    service_ids = {k[0] for k in keys if k[0]}
    user_ids = {k[1] for k in keys if k[1]}
    if not service_ids:
        return {}

    qs = PassbookEntry.objects.filter(
        service_id__in=service_ids,
        user_id__in=user_ids,
        wallet_type=wallet_type,
    )
    if services:
        qs = qs.filter(service__in=services)
    if credit_only:
        qs = qs.filter(credit_amount__gt=Decimal('0'))
    if debit_only:
        qs = qs.filter(debit_amount__gt=Decimal('0'))

    key_set = set(keys)
    out: dict[BalanceKey, PassbookEntry] = {}

    from django.db import connection

    if connection.vendor == 'postgresql':
        entries = (
            qs.only('service_id', 'user_id', 'opening_balance', 'closing_balance', 'created_at')
            .order_by('service_id', 'user_id', '-created_at')
            .distinct('service_id', 'user_id')
        )
        for pe in entries:
            key: BalanceKey = (str(pe.service_id or ''), int(pe.user_id))
            if key in key_set:
                out[key] = pe
    else:
        qs = qs.only('service_id', 'user_id', 'opening_balance', 'closing_balance', 'created_at').order_by(
            '-created_at'
        )
        for pe in qs:
            key = (str(pe.service_id or ''), int(pe.user_id))
            if key in key_set and key not in out:
                out[key] = pe

    return {k: BalancePair.from_entry(out.get(k)) for k in keys}


def _payin_keys_from_items(items: list) -> list[BalanceKey]:
    keys: list[BalanceKey] = []
    for item in items:
        sid = getattr(item, 'service_id', None) or getattr(item, 'transaction_id', None)
        uid = getattr(item, 'user_id', None)
        if sid and uid:
            keys.append((str(sid), int(uid)))
    return keys


def payin_balance_map_for_transactions(transactions: list) -> dict[BalanceKey, BalancePair]:
    keys = _payin_keys_from_items(transactions)
    primary = passbook_balance_map(
        keys,
        wallet_type='main',
        services=['LOAD MONEY', 'LOAD_MONEY'],
        credit_only=True,
    )
    missing = [k for k in keys if not primary[k].opening and not primary[k].closing]
    if not missing:
        return primary
    fallback = passbook_balance_map(missing, wallet_type='main', credit_only=True)
    merged = dict(primary)
    for k in missing:
        if fallback[k].opening or fallback[k].closing:
            merged[k] = fallback[k]
    return merged


def payin_balance_map_for_load_money(items: list) -> dict[BalanceKey, BalancePair]:
    return payin_balance_map_for_transactions(items)


def payout_balance_map(items: list) -> dict[BalanceKey, BalancePair]:
    keys = _payin_keys_from_items(items)
    return passbook_balance_map(keys, wallet_type='main', services=['PAYOUT'], debit_only=True)


def bbps_balance_map(items: list) -> dict[BalanceKey, BalancePair]:
    keys = _payin_keys_from_items(items)
    return passbook_balance_map(keys, wallet_type='bbps', services=['BBPS'], debit_only=True)


def balance_fields_for_key(balance_map: dict[BalanceKey, BalancePair], service_id: str, user_id: int) -> dict[str, str]:
    pair = balance_map.get((str(service_id or ''), int(user_id)), BalancePair.empty())
    return {'opening_balance': pair.opening, 'closing_balance': pair.closing}
