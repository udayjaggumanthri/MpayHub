"""
Resolve BBPS wallet service charge shown on quote / deducted on pay.

Category overrides live on BbpsCategoryWalletCharge. A missing or inactive
row falls back to the active BillAvenueConfig global charge, then to the
Django setting BBPS_SERVICE_CHARGE. Applied amounts are snapshotted on the
payment; this function is not used again at settlement.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import IntegrityError, transaction

from apps.integrations.billavenue.registry import get_active_billavenue_config

_TWO_DP = Decimal('0.01')
_FOUR_DP = Decimal('0.0001')

# primary slug, display name, aliases (compared after the same normalize as the partner app)
BBPS_CANONICAL_CATEGORIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ('agent-collection', 'Agent Collection', ('agentcollection',)),
    ('broadband-postpaid', 'Broadband Postpaid', ('broadband', 'broad-band')),
    ('cable-tv', 'Cable TV', ('cable', 'cabletv')),
    ('clubs-and-associations', 'Clubs and Associations', ('clubs-associations', 'clubs')),
    ('credit-card', 'Credit Card', ('creditcard', 'credit-card-bill', 'cc', 'credit card')),
    ('dth', 'DTH', ('direct-to-home',)),
    ('echallan', 'eChallan', ('e-challan', 'challan')),
    ('education-fees', 'Education Fees', ('education', 'education fee')),
    ('electricity', 'Electricity', ('electric',)),
    ('ev-recharge', 'EV Recharge', ('ev', 'electric-vehicle')),
    ('fastag', 'FASTag', ('fast-tag', 'fast tag', 'fastag recharge')),
    ('fleet-card-recharge', 'Fleet Card Recharge', ('fleet-card', 'fleet card')),
    ('gas', 'Gas', ('piped-gas', 'png')),
    ('housing-society', 'Housing Society', ('housing', 'housing society')),
    ('insurance', 'Insurance', ('life-insurance', 'general-insurance')),
    ('landline-postpaid', 'Landline Postpaid', ('landline', 'land line')),
    ('loan-repayment', 'Loan Repayment', ('loan-emi', 'loan', 'loan repayment')),
    ('lpg-gas', 'LPG Gas', ('lpg', 'lpg gas')),
    ('mobile-postpaid', 'Mobile Postpaid', ('mobile-recharge', 'mobile', 'mobile postpaid')),
    ('mobile-prepaid', 'Mobile Prepaid', ('mobile prepaid', 'prepaid-mobile')),
    ('municipal-services', 'Municipal Services', ('municipal', 'municipality')),
    ('municipal-taxes', 'Municipal Taxes', ('municipal-tax', 'property-tax')),
    ('national-pension-system', 'National Pension System', ('nps', 'pension')),
    ('ncmc-recharge', 'NCMC Recharge', ('ncmc', 'ncmc recharge')),
    ('prepaid-meter', 'Prepaid Meter', ('prepaid', 'smart-meter')),
    ('rental', 'Rental', ('rent', 'rent payment')),
    ('subscription', 'Subscription', ('subscriptions',)),
    ('water', 'Water', ('water bill',)),
)

_PRIMARY_BY_ALIAS: dict[str, str] = {}
_NAME_BY_CODE: dict[str, str] = {}


def _normalize_category_slug(value: str) -> str:
    out = str(value or '').strip().lower().replace('_', '-').replace(' ', '-')
    while '--' in out:
        out = out.replace('--', '-')
    return out.strip('-')


for _code, _name, _aliases in BBPS_CANONICAL_CATEGORIES:
    _NAME_BY_CODE[_code] = _name
    _PRIMARY_BY_ALIAS[_code] = _code
    for _alias in _aliases:
        _PRIMARY_BY_ALIAS[_normalize_category_slug(_alias)] = _code


def canonical_category_code(value: str) -> str:
    """Map a bill_type or MDM label onto the partner category slug."""
    normalized = _normalize_category_slug(value)
    if not normalized:
        return ''
    return _PRIMARY_BY_ALIAS.get(normalized, normalized)


def category_display_name(category_code: str) -> str:
    code = canonical_category_code(category_code)
    if not code:
        return ''
    if code in _NAME_BY_CODE:
        return _NAME_BY_CODE[code]
    return code.replace('-', ' ').title()


def _quantize_money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(_TWO_DP, rounding=ROUND_HALF_UP)


def _quantize_rate(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(_FOUR_DP, rounding=ROUND_HALF_UP)


def _charge_from_parts(*, amount: Decimal, mode: str, flat: Decimal, percent: Decimal) -> Decimal:
    normalized = str(mode or 'FLAT').strip().upper()
    if normalized == 'PERCENT':
        raw = (amount * (percent / Decimal('100'))).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
        return max(Decimal('0'), raw)
    return max(Decimal('0'), flat.quantize(_TWO_DP, rounding=ROUND_HALF_UP))


def _global_charge(*, amount: Decimal) -> dict:
    cfg = get_active_billavenue_config()
    settings_flat = Decimal(str(getattr(settings, 'BBPS_SERVICE_CHARGE', 0) or 0))
    if cfg:
        mode = str(getattr(cfg, 'bbps_wallet_service_charge_mode', '') or 'FLAT').strip().upper()
        flat = Decimal(str(getattr(cfg, 'bbps_wallet_service_charge_flat', None) or 0))
        percent = Decimal(str(getattr(cfg, 'bbps_wallet_service_charge_percent', None) or 0))
        if mode not in ('FLAT', 'PERCENT'):
            mode = 'FLAT'
        charge = _charge_from_parts(amount=amount, mode=mode, flat=flat, percent=percent)
        return {
            'charge': charge,
            'mode': mode.lower(),
            'flat': str(flat),
            'percent': str(percent),
            'source': 'billavenue_config',
            'config_mode': str(getattr(cfg, 'mode', '') or ''),
        }
    charge = max(Decimal('0'), settings_flat.quantize(_TWO_DP, rounding=ROUND_HALF_UP))
    return {
        'charge': charge,
        'mode': 'flat',
        'flat': str(settings_flat),
        'percent': '0',
        'source': 'django_settings',
        'config_mode': '',
    }


def resolve_bbps_wallet_service_charge(*, amount: Decimal, category_code: str = '') -> dict:
    """
    Return wallet-side service charge (not BillAvenue CCF line items).

    Keys:
      - charge: Decimal applied to wallet debit
      - mode: 'flat' | 'percent'
      - flat / percent: configured inputs as strings
      - source: 'category' | 'billavenue_config' | 'django_settings'
      - category_code / category_name: canonical category when one was supplied
    """
    amount = Decimal(str(amount or 0))
    code = canonical_category_code(category_code)
    name = category_display_name(code) if code else ''
    if code:
        from apps.bbps.models import BbpsCategoryWalletCharge

        row = (
            BbpsCategoryWalletCharge.objects.filter(category_code=code)
            .only('mode', 'flat', 'percent', 'is_active')
            .first()
        )
        if row is not None and row.is_active:
            mode = str(row.mode or 'FLAT').strip().upper()
            flat = Decimal(str(row.flat or 0))
            percent = Decimal(str(row.percent or 0))
            if mode not in ('FLAT', 'PERCENT'):
                mode = 'FLAT'
            return {
                'charge': _charge_from_parts(amount=amount, mode=mode, flat=flat, percent=percent),
                'mode': mode.lower(),
                'flat': str(flat),
                'percent': str(percent),
                'source': 'category',
                'category_code': code,
                'category_name': name,
                'config_mode': '',
            }

    resolved = _global_charge(amount=amount)
    resolved['category_code'] = code
    resolved['category_name'] = name
    return resolved


def global_wallet_charge_settings() -> dict:
    """Current default charge inputs, independent of a bill amount."""
    sample = _global_charge(amount=Decimal('0'))
    return {
        'mode': 'PERCENT' if sample['mode'] == 'percent' else 'FLAT',
        'flat': sample['flat'],
        'percent': sample['percent'],
        'source': sample['source'],
        'config_mode': sample.get('config_mode') or '',
    }


def list_wallet_charge_catalog() -> dict:
    """Canonical categories plus any saved codes outside that list."""
    from apps.bbps.models import BbpsCategoryWalletCharge

    rules = {
        row.category_code: row
        for row in BbpsCategoryWalletCharge.objects.all()
    }
    default = global_wallet_charge_settings()
    preview_amount = Decimal('100')
    categories = []
    seen = set()
    for code, name, _aliases in BBPS_CANONICAL_CATEGORIES:
        seen.add(code)
        categories.append(_catalog_row(code, name, rules.get(code), default, preview_amount))
    for code in sorted(set(rules) - seen):
        categories.append(
            _catalog_row(code, category_display_name(code), rules.get(code), default, preview_amount)
        )
    return {'default': default, 'categories': categories}


def _catalog_row(code: str, name: str, row, default: dict, preview_amount: Decimal) -> dict:
    active = bool(row and row.is_active)
    if active:
        mode = str(row.mode or 'FLAT').upper()
        flat = str(row.flat)
        percent = str(row.percent)
        source = 'category'
        effective_mode = mode
        effective_flat = flat
        effective_percent = percent
    else:
        mode = str(row.mode or default['mode']).upper() if row else default['mode']
        flat = str(row.flat) if row else default['flat']
        percent = str(row.percent) if row else default['percent']
        source = default['source']
        effective_mode = default['mode']
        effective_flat = default['flat']
        effective_percent = default['percent']
    effective_charge = _charge_from_parts(
        amount=preview_amount,
        mode=effective_mode,
        flat=Decimal(effective_flat or 0),
        percent=Decimal(effective_percent or 0),
    )
    return {
        'category_code': code,
        'display_name': name,
        'has_override': active,
        'is_active': active,
        'mode': mode if mode in ('FLAT', 'PERCENT') else 'FLAT',
        'flat': flat,
        'percent': percent,
        'effective_mode': effective_mode,
        'effective_flat': effective_flat,
        'effective_percent': effective_percent,
        'effective_source': source,
        'preview_amount': str(preview_amount),
        'preview_charge': str(effective_charge),
    }


class WalletChargeValidationError(ValueError):
    def __init__(self, errors: dict):
        super().__init__('Invalid wallet service charge')
        self.errors = errors


def _parse_optional_decimal(value, label):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, f'Enter a {label}. Use 0 if this charge should be zero.'
    try:
        return _quantize_rate(value), None
    except Exception:
        return None, 'Enter a valid number.'


def _parse_charge_inputs(*, mode, flat, percent) -> tuple[str, Decimal, Decimal]:
    normalized = str(mode or '').strip().upper()
    errors = {}
    if normalized not in ('FLAT', 'PERCENT'):
        errors['mode'] = 'Choose FLAT or PERCENT.'
    flat_dec, flat_error = _parse_optional_decimal(flat, 'flat amount')
    percent_dec, percent_error = _parse_optional_decimal(percent, 'percent')
    if flat_error:
        errors['flat'] = flat_error
    if percent_error:
        errors['percent'] = percent_error
    if flat_dec is not None and flat_dec < 0:
        errors['flat'] = 'Flat charge cannot be negative.'
    if percent_dec is not None and (percent_dec < 0 or percent_dec > 100):
        errors['percent'] = 'Percent must be between 0 and 100.'
    if errors:
        raise WalletChargeValidationError(errors)
    return normalized, flat_dec, percent_dec


def update_global_wallet_service_charge(*, mode, flat, percent) -> dict:
    """Write the default charge on the active BillAvenue config only."""
    normalized, flat_dec, percent_dec = _parse_charge_inputs(mode=mode, flat=flat, percent=percent)
    cfg = get_active_billavenue_config()
    if cfg is None:
        raise WalletChargeValidationError({
            'default': 'No active BillAvenue config. Activate UAT or Production before changing the default charge.',
        })
    from apps.integrations.models import BillAvenueConfig

    with transaction.atomic():
        locked = BillAvenueConfig.objects.select_for_update().get(pk=cfg.pk)
        locked.bbps_wallet_service_charge_mode = normalized
        locked.bbps_wallet_service_charge_flat = flat_dec
        locked.bbps_wallet_service_charge_percent = percent_dec
        locked.save(update_fields=[
            'bbps_wallet_service_charge_mode',
            'bbps_wallet_service_charge_flat',
            'bbps_wallet_service_charge_percent',
            'updated_at',
        ])
    return global_wallet_charge_settings()


def upsert_category_wallet_charge(*, category_code, mode, flat, percent, is_active, user) -> dict:
    """Insert or update one category rule. Inactive rules fall back to the default."""
    code = canonical_category_code(category_code)
    if not code or len(code) > 80:
        raise WalletChargeValidationError({'category_code': 'Choose a category.'})
    normalized, flat_dec, percent_dec = _parse_charge_inputs(mode=mode, flat=flat, percent=percent)
    active = bool(is_active)
    from apps.bbps.models import BbpsCategoryWalletCharge

    with transaction.atomic():
        row = BbpsCategoryWalletCharge.objects.select_for_update().filter(category_code=code).first()
        if row is None:
            try:
                with transaction.atomic():
                    row = BbpsCategoryWalletCharge.objects.create(
                        category_code=code,
                        mode=normalized,
                        flat=flat_dec,
                        percent=percent_dec,
                        is_active=active,
                        updated_by=user if getattr(user, 'pk', None) else None,
                    )
            except IntegrityError:
                row = BbpsCategoryWalletCharge.objects.select_for_update().get(category_code=code)
        if row.pk and (
            row.mode != normalized
            or row.flat != flat_dec
            or row.percent != percent_dec
            or row.is_active != active
            or row.updated_by_id != getattr(user, 'pk', None)
        ):
            row.mode = normalized
            row.flat = flat_dec
            row.percent = percent_dec
            row.is_active = active
            row.updated_by = user if getattr(user, 'pk', None) else None
            row.save(update_fields=['mode', 'flat', 'percent', 'is_active', 'updated_by', 'updated_at'])
    return _catalog_row(
        code,
        category_display_name(code),
        row,
        global_wallet_charge_settings(),
        Decimal('100'),
    )


__all__ = [
    'BBPS_CANONICAL_CATEGORIES',
    'WalletChargeValidationError',
    'canonical_category_code',
    'category_display_name',
    'get_active_billavenue_config',
    'global_wallet_charge_settings',
    'list_wallet_charge_catalog',
    'resolve_bbps_wallet_service_charge',
    'update_global_wallet_service_charge',
    'upsert_category_wallet_charge',
]
