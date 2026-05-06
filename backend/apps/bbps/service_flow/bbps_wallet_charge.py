"""
Resolve BBPS wallet service charge shown on quote / deducted on pay.

Charge is admin-configured on the active BillAvenueConfig (BillAvenue / BBPS API settings).
Falls back to Django setting BBPS_SERVICE_CHARGE when no active config exists.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

from apps.integrations.models import BillAvenueConfig

_TWO_DP = Decimal('0.01')


def get_active_billavenue_config() -> BillAvenueConfig | None:
    return BillAvenueConfig.objects.filter(is_deleted=False, enabled=True, is_active=True).first()


def resolve_bbps_wallet_service_charge(*, amount: Decimal) -> dict:
    """
    Return wallet-side service charge (not BillAvenue CCF line items).

    Keys:
      - charge: Decimal applied to wallet debit
      - mode: 'flat' | 'percent'
      - flat: str decimal
      - percent: str decimal (percent of bill amount when mode is percent)
      - source: 'billavenue_config' | 'django_settings'
    """
    cfg = get_active_billavenue_config()
    settings_flat = Decimal(str(getattr(settings, 'BBPS_SERVICE_CHARGE', 0) or 0))

    if cfg:
        mode = str(getattr(cfg, 'bbps_wallet_service_charge_mode', '') or 'FLAT').strip().upper()
        flat = Decimal(str(getattr(cfg, 'bbps_wallet_service_charge_flat', None)))
        percent = Decimal(str(getattr(cfg, 'bbps_wallet_service_charge_percent', None) or 0))
        if mode not in ('FLAT', 'PERCENT'):
            mode = 'FLAT'
        if mode == 'PERCENT':
            raw = (amount * (percent / Decimal('100'))).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
            charge = max(Decimal('0'), raw)
        else:
            charge = max(Decimal('0'), flat.quantize(_TWO_DP, rounding=ROUND_HALF_UP))
        return {
            'charge': charge,
            'mode': mode.lower(),
            'flat': str(flat),
            'percent': str(percent),
            'source': 'billavenue_config',
        }

    charge = max(Decimal('0'), settings_flat.quantize(_TWO_DP, rounding=ROUND_HALF_UP))
    return {
        'charge': charge,
        'mode': 'flat',
        'flat': str(settings_flat),
        'percent': '0',
        'source': 'django_settings',
    }
