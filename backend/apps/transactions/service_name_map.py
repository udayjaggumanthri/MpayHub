"""Map internal service_id prefixes to friendly labels for enterprise reports."""

from __future__ import annotations

PREFIX_LABELS = (
    ('PMLM', 'Pay-in (Load Money)'),
    ('PMPI', 'Pay-in'),
    ('PMPO', 'Pay-out'),
    ('PMBBPS', 'BBPS'),
    ('PMWT', 'Wallet transfer'),
)


def service_display_name(service_id: str | None) -> str:
    sid = (service_id or '').strip().upper()
    if not sid:
        return 'Unknown'
    for prefix, label in PREFIX_LABELS:
        if sid.startswith(prefix):
            return label
    return 'Other service'


def service_family_from_service_id(service_id: str | None) -> str:
    sid = (service_id or '').strip().upper()
    if sid.startswith(('PMLM', 'PMPI')):
        return 'payin'
    if sid.startswith('PMPO'):
        return 'payout'
    if sid.startswith('PMBBPS'):
        return 'bbps'
    if sid.startswith('PMWT'):
        return 'wallet_transfer'
    return 'other'
