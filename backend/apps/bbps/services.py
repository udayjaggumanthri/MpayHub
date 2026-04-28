"""BBPS business logic services."""
from django.db import models, transaction as db_transaction
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from apps.bbps.models import (
    BbpsBillerInputParam,
    BbpsBillerMaster,
    BbpsCategoryCommissionRule,
    BbpsProviderBillerMap,
    BbpsServiceCategory,
)
from apps.integrations.bbps_client import BBPSClient
import random
import string


BBPS_CATEGORY_ALIASES = {
    'mobile': 'mobile-recharge',
    'creditcard': 'credit-card',
    'credit-card-bill': 'credit-card',
    'cc': 'credit-card',
    'broad-band': 'broadband',
    'landline-postpaid': 'landline',
}

ALLOWED_BILLER_STATUSES = {'ACTIVE', 'ENABLED', 'FLUCTUATING'}


def normalize_category_code(category: str) -> str:
    out = str(category or '').strip().lower().replace('_', '-')
    return BBPS_CATEGORY_ALIASES.get(out, out)


def _active_commission_category_codes() -> set[str]:
    return set(
        BbpsCategoryCommissionRule.objects.filter(is_deleted=False, is_active=True)
        .values_list('category__code', flat=True)
    )


def _stale_block_enabled() -> bool:
    return bool(getattr(settings, 'BBPS_BLOCK_STALE_BILLERS', False))


def governance_block_reasons_for_map(map_row) -> list[str]:
    reasons = []
    biller_status = str(getattr(map_row.biller_master, 'biller_status', '') or '').upper()
    if not map_row.provider.category.is_active:
        reasons.append('category_inactive')
    if not map_row.provider.is_active:
        reasons.append('provider_inactive')
    if not map_row.is_active:
        reasons.append('map_inactive')
    if biller_status not in ALLOWED_BILLER_STATUSES:
        reasons.append('biller_status')
    if _stale_block_enabled() and getattr(map_row.biller_master, 'is_stale', False):
        reasons.append('stale')
    has_rule = BbpsCategoryCommissionRule.objects.filter(
        is_deleted=False,
        is_active=True,
        category=map_row.provider.category,
    ).exists()
    if not has_rule:
        reasons.append('no_rule')
    return reasons


def governance_readiness_for_biller(biller_id: str) -> dict:
    row = (
        BbpsProviderBillerMap.objects.filter(
            is_deleted=False,
            provider__is_deleted=False,
            provider__category__is_deleted=False,
            biller_master__is_deleted=False,
            biller_master__biller_id=biller_id,
        )
        .select_related('provider__category', 'biller_master')
        .first()
    )
    if not row:
        return {'allowed': False, 'blocked_by': ['map_missing']}
    blocked = governance_block_reasons_for_map(row)
    return {'allowed': not blocked, 'blocked_by': blocked}


def calculate_bbps_charge(amount):
    """
    Calculate BBPS service charge (fixed ₹5.00).
    
    Args:
        amount: Bill amount
    
    Returns:
        dict with charge and total_deducted
    """
    charge = Decimal(str(settings.BBPS_SERVICE_CHARGE))
    total_deducted = amount + charge
    
    return {
        'charge': charge,
        'total_deducted': total_deducted
    }


def generate_request_id():
    """Generate a unique request ID for BBPS transactions."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=20))


def fetch_bill(*args, **kwargs):
    """Legacy path intentionally disabled after BillAvenue hard cutover."""
    raise RuntimeError('Legacy BBPS fetch_bill() path disabled. Use service_flow.fetch_bill_with_cache().')


@db_transaction.atomic
def process_bill_payment(*args, **kwargs):
    """Legacy path intentionally disabled after BillAvenue hard cutover."""
    raise RuntimeError('Legacy BBPS process_bill_payment() path disabled. Use service_flow.process_bill_payment_flow().')


def get_bill_categories():
    """Get list of categories from governance catalog only."""
    rows = BbpsServiceCategory.objects.filter(is_deleted=False, is_active=True).order_by('display_order', 'name')
    active_rule_codes = _active_commission_category_codes()
    rows = [row for row in rows if row.code in active_rule_codes]
    return [{'id': normalize_category_code(r.code), 'name': r.name} for r in rows]


def get_billers_by_category(category):
    """Get billers for a specific category from provider-mapped biller master only."""
    norm = normalize_category_code(category)
    mapped = BbpsProviderBillerMap.objects.filter(
        is_deleted=False,
        is_active=True,
        provider__is_deleted=False,
        provider__is_active=True,
        provider__category__is_deleted=False,
        provider__category__is_active=True,
        provider__category__code__iexact=norm,
        biller_master__is_deleted=False,
    ).select_related('biller_master')
    if norm not in _active_commission_category_codes():
        return []
    biller_ids = [m.biller_master.biller_id for m in mapped]
    if biller_ids:
        masters = (
            BbpsBillerMaster.objects.filter(
                is_deleted=False,
                biller_id__in=biller_ids,
                biller_status__in=ALLOWED_BILLER_STATUSES,
            )
            .order_by('biller_name')
        )
        if _stale_block_enabled():
            masters = masters.filter(is_stale=False)
        return [
            {
                'id': m.pk,
                'biller_id': m.biller_id,
                'name': m.biller_name,
                'biller_name': m.biller_name,
                'category': m.biller_category,
                'status': m.biller_status,
                'fetch_requirement': m.biller_fetch_requirement,
                'last_synced_at': m.last_synced_at,
            }
            for m in masters
        ]
    return []


def get_biller_input_schema(biller_id: str) -> list[dict]:
    master = BbpsBillerMaster.objects.filter(is_deleted=False, biller_id=biller_id).first()
    if not master:
        return []
    params = BbpsBillerInputParam.objects.filter(is_deleted=False, biller=master).order_by('display_order', 'id')
    return [
        {
            'param_name': p.param_name,
            'data_type': p.data_type,
            'is_optional': p.is_optional,
            'min_length': p.min_length,
            'max_length': p.max_length,
            'regex': p.regex,
            'visibility': p.visibility,
            'default_values': p.default_values,
        }
        for p in params
    ]


def get_providers_by_category(category):
    """List service providers with mapped billers for the category."""
    norm = normalize_category_code(category)
    cache_key = f'bbps:providers:{norm}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    maps = BbpsProviderBillerMap.objects.filter(
        is_deleted=False,
        is_active=True,
        provider__is_deleted=False,
        provider__is_active=True,
        provider__category__is_deleted=False,
        provider__category__is_active=True,
        provider__category__code__iexact=norm,
        biller_master__is_deleted=False,
        biller_master__biller_status__in=ALLOWED_BILLER_STATUSES,
    ).select_related('provider', 'provider__category', 'biller_master').order_by(
        'provider__priority', 'priority', 'provider__name'
    )
    if _stale_block_enabled():
        maps = maps.filter(biller_master__is_stale=False)
    if norm not in _active_commission_category_codes():
        cache.set(cache_key, [], timeout=300)
        return []
    out = {}
    for row in maps:
        p = row.provider
        key = p.pk
        if key not in out:
            out[key] = {
                'provider_id': p.pk,
                'provider_code': p.code,
                'provider_name': p.name,
                'provider_type': p.provider_type,
                'category': p.category.code,
                'biller_options': [],
            }
        out[key]['biller_options'].append(
            {
                'map_id': row.pk,
                'biller_id': row.biller_master.biller_id,
                'biller_name': row.biller_master.biller_name,
                'biller_category': row.biller_master.biller_category,
                'priority': row.priority,
            }
        )
    payload = list(out.values())
    cache.set(cache_key, payload, timeout=300)
    return payload


def get_setup_readiness() -> dict:
    from apps.integrations.models import BillAvenueAgentProfile, BillAvenueConfig  # local import to avoid circulars

    cfg = BillAvenueConfig.objects.filter(is_deleted=False, enabled=True, is_active=True).first()
    profile_count = 0
    if cfg:
        profile_count = BillAvenueAgentProfile.objects.filter(config=cfg, is_deleted=False, enabled=True).count()

    mdm_count = BbpsBillerMaster.objects.filter(is_deleted=False).count()
    provider_count = BbpsProviderBillerMap.objects.filter(
        is_deleted=False,
        provider__is_deleted=False,
        provider__is_active=True,
    ).values('provider_id').distinct().count()
    mapping_count = BbpsProviderBillerMap.objects.filter(is_deleted=False, is_active=True).count()
    active_rule_count = BbpsCategoryCommissionRule.objects.filter(is_deleted=False, is_active=True).count()
    active_rules_by_category = list(
        BbpsCategoryCommissionRule.objects.filter(is_deleted=False, is_active=True)
        .values('category__code')
        .order_by('category__code')
        .annotate(count=models.Count('id'))
    )

    checks = [
        {'key': 'active_config', 'ok': bool(cfg), 'message': 'Active enabled BillAvenue config'},
        {'key': 'agent_profile', 'ok': profile_count > 0, 'message': 'At least one enabled agent profile'},
        {'key': 'mdm_billers', 'ok': mdm_count > 0, 'message': 'MDM biller cache available'},
        {'key': 'providers', 'ok': provider_count > 0, 'message': 'Provider master has entries'},
        {'key': 'mappings', 'ok': mapping_count > 0, 'message': 'Provider-biller mappings exist'},
        {'key': 'commission_rules', 'ok': active_rule_count > 0, 'message': 'At least one active commission rule'},
    ]
    ok_count = len([c for c in checks if c['ok']])
    blockers = [c['key'] for c in checks if not c['ok']]
    return {
        'score_percent': int((ok_count / len(checks)) * 100),
        'checks': checks,
        'go_live_blocked': bool(blockers),
        'go_live_blockers': blockers,
        'stats': {
            'enabled_active_config_id': cfg.pk if cfg else None,
            'agent_profile_count': profile_count,
            'mdm_biller_count': mdm_count,
            'provider_count': provider_count,
            'mapping_count': mapping_count,
            'active_commission_rule_count': active_rule_count,
            'active_rules_by_category': active_rules_by_category,
        },
    }
