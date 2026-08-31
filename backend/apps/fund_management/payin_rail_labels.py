"""Collection rail labels for pay-in (gateway vs manual QR)."""
from __future__ import annotations

from apps.fund_management.models import LoadMoney


def payin_collection_rail(obj: LoadMoney) -> str:
    return (getattr(obj, 'collection_rail', None) or 'gateway').strip().lower()


def payin_is_qr_rail(obj: LoadMoney) -> bool:
    return payin_collection_rail(obj) == 'qr'


def payin_qr_account_label(obj: LoadMoney) -> str:
    qr = getattr(obj, 'pay_in_qr_account', None)
    name = str(getattr(qr, 'display_name', '') or '').strip()
    if name:
        return name
    return str(getattr(obj, 'gateway', '') or '').strip()


def payin_gateway_provider_name(obj: LoadMoney) -> str:
    """Payment gateway name for gateway-rail rows only."""
    selected_pg = getattr(obj, 'payment_gateway', None)
    if selected_pg is not None and getattr(selected_pg, 'name', None):
        return str(selected_pg.name).strip()
    pkg = getattr(obj, 'package', None)
    if pkg:
        pg = getattr(pkg, 'payment_gateway', None)
        if pg is not None and getattr(pg, 'name', None):
            return str(pg.name).strip()
        prov = (getattr(pkg, 'provider', '') or '').strip().lower()
        if prov == 'razorpay':
            return 'Razorpay'
        if prov == 'payu':
            return 'PayU'
        if prov == 'mock':
            return 'Mock (test)'
        label = (pkg.display_name or pkg.code or '').strip()
        if label:
            return label
    gateway = str(getattr(obj, 'gateway', '') or '').strip()
    if gateway:
        return gateway.replace('_', ' ').title()
    return '—'


def payin_collection_method_label(obj: LoadMoney) -> str:
    """Human label for reports: QR account name or gateway provider."""
    if payin_is_qr_rail(obj):
        return payin_qr_account_label(obj) or 'Manual QR'
    return payin_gateway_provider_name(obj)


def payin_rail_type_label(obj: LoadMoney) -> str:
    return 'Manual QR' if payin_is_qr_rail(obj) else 'Payment Gateway'
