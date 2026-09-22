"""
Validate CommissionLedger.meta on create paths used for team / source attribution reporting.
Fail closed on invalid new rows; do not rewrite historical DB rows.
"""
from __future__ import annotations


def validate_commission_ledger_meta(meta, *, source: str, wallet_type: str) -> dict:
    """
    Ensure pay-in related ledger rows carry source_user_id for downstream reports.

    - ``source='payin'``: chain commission; requires positive ``source_user_id``.
    - ``source='profit'``: platform slices tied to a payer; requires ``source_user_id``.
    - Other modules (bbps/payout/bank_verification/…): require ``source_user_id`` when present.
    """
    if meta is not None and not isinstance(meta, dict):
        raise ValueError('CommissionLedger.meta must be a dict or None')

    m = dict(meta or {})

    if source == 'payin':
        _require_source_user_id(m, context='payin commission')
    elif source == 'profit':
        _require_source_user_id(m, context='payin platform profit')
    elif source in ('bbps', 'payout', 'bank_verification', 'aeps', 'cms'):
        if m.get('source_user_id') is not None:
            _require_source_user_id(m, context=f'{source} fee')

    return m


def _require_source_user_id(m: dict, *, context: str) -> None:
    suid = m.get('source_user_id')
    if suid is None:
        raise ValueError(f'{context} ledger meta requires source_user_id')
    if isinstance(suid, bool):
        raise ValueError(f'{context} ledger meta requires integer source_user_id')
    if isinstance(suid, int):
        if suid <= 0:
            raise ValueError(f'{context} ledger meta requires a positive integer source_user_id')
        return
    if isinstance(suid, str) and suid.isdigit() and int(suid) > 0:
        return
    raise ValueError(f'{context} ledger meta requires a positive integer source_user_id')


def commission_ledger_create(**kwargs):
    """Create a CommissionLedger row after validating ``meta`` for the given source/wallet_type."""
    from apps.transactions.models import CommissionLedger

    meta = kwargs.pop('meta', None)
    src = kwargs.get('source') or 'payin'
    wt = kwargs.get('wallet_type') or 'main'
    validated = validate_commission_ledger_meta(meta, source=src, wallet_type=wt)
    kwargs['meta'] = validated
    return CommissionLedger.objects.create(**kwargs)
