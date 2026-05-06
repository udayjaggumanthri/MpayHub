"""BBPS business logic services."""
from django.db import models, transaction as db_transaction
from django.db.models import Q
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from apps.bbps.mdm_param_utils import infer_input_kind, normalize_schema_choices
from apps.bbps.models import (
    BbpsBillerAdditionalInfoSchema,
    BbpsBillerInputParam,
    BbpsBillerMaster,
    BbpsBillerPaymentChannelLimit,
    BbpsBillerPaymentModeLimit,
    BbpsBillerPlanMeta,
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


def _normalize_text(value: str) -> str:
    return str(value or '').strip()


def normalize_category_code(category: str) -> str:
    out = str(category or '').strip().lower().replace('_', '-').replace(' ', '-')
    while '--' in out:
        out = out.replace('--', '-')
    return BBPS_CATEGORY_ALIASES.get(out, out)


def _category_lookup_values(category: str) -> set[str]:
    """
    Accept both normalized and legacy stored category codes.
    Example: credit-card <-> credit card.
    """
    norm = normalize_category_code(category)
    vals = {norm}
    if '-' in norm:
        vals.add(norm.replace('-', ' '))
    if ' ' in norm:
        vals.add(norm.replace(' ', '-'))
    vals.add(norm.replace('-', '').replace(' ', ''))
    return {v for v in vals if v}


def _active_commission_category_codes() -> set[str]:
    return set(
        normalize_category_code(code)
        for code in BbpsCategoryCommissionRule.objects.filter(is_deleted=False, is_active=True)
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
    if not getattr(map_row.biller_master, 'is_active_local', True):
        reasons.append('local_inactive')
    if bool(getattr(map_row.biller_master, 'soft_deleted_at', None)):
        reasons.append('soft_deleted')
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
    row = BbpsBillerMaster.objects.filter(
        is_deleted=False,
        biller_id=biller_id,
    ).first()
    if not row:
        return {'allowed': False, 'blocked_by': ['biller_missing']}
    blocked = []
    if not row.is_active_local:
        blocked.append('local_inactive')
    if bool(row.soft_deleted_at):
        blocked.append('soft_deleted')
    if str(row.biller_status or '').upper() not in ALLOWED_BILLER_STATUSES:
        blocked.append('biller_status')
    if _stale_block_enabled() and getattr(row, 'is_stale', False):
        blocked.append('stale')
    return {'allowed': not blocked, 'blocked_by': blocked}


def calculate_bbps_charge(amount):
    """
    Calculate BBPS wallet service charge (admin BillAvenue config or BBPS_SERVICE_CHARGE fallback).

    Args:
        amount: Bill amount

    Returns:
        dict with charge and total_deducted
    """
    from apps.bbps.service_flow.bbps_wallet_charge import resolve_bbps_wallet_service_charge

    info = resolve_bbps_wallet_service_charge(amount=Decimal(str(amount)))
    charge = info['charge']
    total_deducted = Decimal(str(amount)) + charge

    return {
        'charge': charge,
        'total_deducted': total_deducted,
        'mode': info.get('mode'),
        'source': info.get('source'),
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
    """Get categories strictly from currently visible billers."""
    visible_qs = BbpsBillerMaster.objects.filter(
        is_deleted=False,
        biller_status__in=ALLOWED_BILLER_STATUSES,
        is_active_local=True,
        soft_deleted_at__isnull=True,
    )
    if _stale_block_enabled():
        visible_qs = visible_qs.filter(is_stale=False)
    visible_codes = {
        normalize_category_code(code)
        for code in visible_qs.values_list('biller_category', flat=True)
        if str(code or '').strip()
    }
    allowed_codes = sorted(visible_codes)
    if not allowed_codes:
        return []
    name_map = {
        normalize_category_code(row.code): row.name
        for row in BbpsServiceCategory.objects.filter(is_deleted=False, is_active=True)
    }
    return [{'id': code, 'name': name_map.get(code, to_title_case(code))} for code in allowed_codes]


def to_title_case(value: str) -> str:
    cleaned = str(value or '').replace('-', ' ').replace('_', ' ').strip()
    return ' '.join(word.capitalize() for word in cleaned.split())


def get_billers_by_category(category):
    """Get billers for a specific category directly from biller master visibility flags."""
    lookup_values = _category_lookup_values(category)
    category_filter = Q()
    for val in lookup_values:
        category_filter |= Q(biller_category__iexact=val)
    masters = (
        BbpsBillerMaster.objects.filter(
            is_deleted=False,
            biller_status__in=ALLOWED_BILLER_STATUSES,
            is_active_local=True,
            soft_deleted_at__isnull=True,
        )
        .filter(category_filter)
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


def _payment_channel_ui_label(code: str) -> str:
    c = str(code or '').strip().upper()
    labels = {
        'AGT': 'AGT — Agent-assisted (retail counter)',
        'MOB': 'MOB — Mobile app',
        'MOBB': 'MOBB — Mobile (alternate)',
        'INT': 'INT — Internet',
        'INTB': 'INTB — Internet (alternate)',
        'POS': 'POS — Point of sale',
    }
    return labels.get(c, c or 'Channel')


# Prefer terminal-safe channels for assisted (B2B-style) flows; MOB/INT need proper initChannel + device fields.
_UI_AUTO_CHANNEL_PRIORITY = ('AGT', 'POS')


def _biller_category_assisted_card_like(raw: str) -> bool:
    """True for credit-card and loan-repayment style MDM labels (BillAvenue E078 on POS for some instruments)."""
    s = ' '.join(str(raw or '').strip().lower().replace('_', ' ').replace('-', ' ').split())
    if 'credit' in s and 'card' in s:
        return True
    if 'loan' in s and 'repay' in s:
        return True
    return s in ('credit card', 'loan repayment')


def get_biller_payment_ui_options(biller_id: str) -> dict:
    """
    Payment channels/modes for UI: from BillAvenue MDM rows on the biller, intersected with
    NPCI BBPS channel-vs-instrument rules (see ``display_payment_modes_for_channel``).
    """
    from apps.bbps.service_flow.compliance import display_payment_modes_for_channel
    from apps.bbps.service_flow.payment_ui_policy import (
        assisted_card_offer_agt_cash_only,
        mdm_labels_with_implicit_cash_for_agt,
    )
    from apps.bbps.service_flow.provider_policy import provider_policy_decision_for_combo

    master = BbpsBillerMaster.objects.filter(
        is_deleted=False,
        biller_id=biller_id,
        is_active_local=True,
        soft_deleted_at__isnull=True,
    ).first()
    if not master:
        return {
            'payment_channels': [],
            'payment_modes_by_channel': {},
            'payment_modes': [],
            'payment_mode_channel_map': {},
            'default_channel': '',
            'default_payment_mode': '',
            'source': 'none',
        }

    channels = list(
        BbpsBillerPaymentChannelLimit.objects.filter(
            is_deleted=False, biller=master, is_active=True
        ).order_by('payment_channel')
    )
    modes = list(
        BbpsBillerPaymentModeLimit.objects.filter(
            is_deleted=False, biller=master, is_active=True
        ).order_by('payment_mode')
    )

    ch_codes = [_normalize_text(c.payment_channel).upper() for c in channels if c.payment_channel]
    if not ch_codes:
        ch_codes = ['AGT']
    ui_channel_codes = [ch for ch in _UI_AUTO_CHANNEL_PRIORITY if ch in ch_codes]

    mdm_mode_labels = [m.payment_mode for m in modes if m.payment_mode]
    mdm_for_display = mdm_mode_labels if mdm_mode_labels else None

    offer_agt_cash_only = assisted_card_offer_agt_cash_only(master, ch_codes, mdm_mode_labels)

    # Credit / loan: AGT + Cash only when policy says MDM implied POS modes but omitted Cash on AGT (typical B2B).
    # Legacy strict MDM intersection remains behind BBPS_ASSISTED_CARD_PAYMENT_UI=mdm_strict.
    if offer_agt_cash_only:
        ui_channel_codes = ['AGT']
        eff_labels = mdm_labels_with_implicit_cash_for_agt(mdm_mode_labels)
        mdm_for_display_eff = eff_labels
    else:
        mdm_for_display_eff = mdm_for_display
        # Credit / loan: prefer AGT-only when MDM lists at least one AGT-valid instrument (e.g. Cash).
        if (
            _biller_category_assisted_card_like(getattr(master, 'biller_category', '') or '')
            and 'AGT' in ch_codes
            and display_payment_modes_for_channel('AGT', mdm_for_display)
        ):
            ui_channel_codes = ['AGT']

    modes_by_channel: dict[str, list[str]] = {}
    for ch in ui_channel_codes:
        shown = display_payment_modes_for_channel(ch, mdm_for_display_eff)
        if ch == 'AGT' and not shown and not mdm_mode_labels:
            shown = ['Cash']
        shown = [
            mode
            for mode in shown
            if provider_policy_decision_for_combo(
                biller_id=getattr(master, 'biller_id', ''),
                biller_category=getattr(master, 'biller_category', ''),
                payment_mode=mode,
                payment_channel=ch,
            ) is not False
        ]
        modes_by_channel[ch] = shown

    mode_channel_map: dict[str, str] = {}
    ordered_modes: list[str] = []
    for ch in ui_channel_codes:
        for mode in (modes_by_channel.get(ch) or []):
            if mode not in mode_channel_map:
                mode_channel_map[mode] = ch
            if mode not in ordered_modes:
                ordered_modes.append(mode)

    default_ch = mode_channel_map.get(ordered_modes[0], '') if ordered_modes else ''
    default_mode = ordered_modes[0] if ordered_modes else ''

    payment_channels = [
        {
            'code': _normalize_text(c.payment_channel).upper(),
            'label': _payment_channel_ui_label(c.payment_channel),
            'min_amount': str(c.min_amount or 0),
            'max_amount': str(c.max_amount or 0),
        }
        for c in channels
        if c.payment_channel
    ]
    if not payment_channels:
        payment_channels = [{'code': 'AGT', 'label': _payment_channel_ui_label('AGT'), 'min_amount': '0', 'max_amount': '0'}]

    if offer_agt_cash_only:
        payment_channels = [p for p in payment_channels if p.get('code') == 'AGT']

    if not channels and not modes:
        src = 'bbps_defaults'
    elif ordered_modes:
        src = 'mdm_and_bbps'
    else:
        src = 'requires_device_context'

    return {
        'payment_channels': payment_channels,
        'payment_modes_by_channel': modes_by_channel,
        'payment_modes': ordered_modes,
        'payment_mode_channel_map': mode_channel_map,
        'default_channel': default_ch,
        'default_payment_mode': default_mode,
        'source': src,
    }


def get_biller_input_schema(biller_id: str) -> list[dict]:
    master = BbpsBillerMaster.objects.filter(
        is_deleted=False,
        biller_id=biller_id,
        is_active_local=True,
        soft_deleted_at__isnull=True,
    ).first()
    if not master:
        return []
    params = BbpsBillerInputParam.objects.filter(is_deleted=False, biller=master).order_by('display_order', 'id')
    rows = []
    for p in params:
        choices = normalize_schema_choices(p.default_values)
        extras = p.mdm_extras if isinstance(getattr(p, 'mdm_extras', None), dict) else {}
        help_text = str(extras.get('help_text') or '').strip()
        input_kind = infer_input_kind(data_type=p.data_type or '', choices=choices)
        rows.append(
            {
                'param_name': p.param_name,
                'data_type': p.data_type,
                'is_optional': p.is_optional,
                'min_length': p.min_length,
                'max_length': p.max_length,
                'regex': p.regex,
                'visibility': p.visibility,
                'default_values': p.default_values,
                'choices': choices,
                'help_text': help_text,
                'input_kind': input_kind,
                'canonical_key': _canonical_input_key(p.param_name),
                'send_in_input_params': True,
            }
        )
    # Do not inject a synthetic "Mobile Number" when MDM does not list it — some
    # billers (e.g. DTH dummy) only expose Customer ID. Fetch/pay still send
    # customerMobile from the authenticated user's phone when the client omits it.
    return rows


def get_biller_additional_info_schema(biller_id: str) -> dict[str, list[dict]]:
    """Group MDM additional-info / plan-additional tags by info_group for the schema API."""
    master = BbpsBillerMaster.objects.filter(
        is_deleted=False,
        biller_id=biller_id,
        soft_deleted_at__isnull=True,
    ).first()
    if not master:
        return {}
    rows = (
        BbpsBillerAdditionalInfoSchema.objects.filter(is_deleted=False, biller=master)
        .order_by('info_group', 'info_name')
        .values('info_group', 'info_name', 'data_type', 'is_optional')
    )
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        grp = str(r.get('info_group') or 'additional')
        grouped.setdefault(grp, []).append(
            {
                'info_name': r.get('info_name'),
                'data_type': r.get('data_type'),
                'is_optional': r.get('is_optional'),
            }
        )
    return grouped


def get_biller_plans_lite(biller_id: str, *, limit: int = 100) -> tuple[list[dict], bool]:
    """Active plan rows for pay UI (plan-mandatory billers). Returns (rows, truncated)."""
    master = BbpsBillerMaster.objects.filter(
        is_deleted=False,
        biller_id=biller_id,
        soft_deleted_at__isnull=True,
    ).first()
    if not master:
        return [], False
    qs = (
        BbpsBillerPlanMeta.objects.filter(is_deleted=False, biller=master)
        .filter(Q(status__iexact='ACTIVE') | Q(status=''))
        .order_by('amount_in_rupees', 'plan_id')
    )
    total = qs.count()
    truncated = total > limit
    out = []
    for p in qs[:limit]:
        out.append(
            {
                'plan_id': str(p.plan_id or '').strip(),
                'plan_desc': str(p.plan_desc or '').strip(),
                'amount_in_rupees': str(p.amount_in_rupees or '0'),
                'category_type': str(p.category_type or '').strip(),
                'status': str(p.status or '').strip(),
            }
        )
    return out, truncated


def _canonical_input_key(param_name: str) -> str:
    normalized = str(param_name or '').strip().lower().replace('_', ' ').replace('-', ' ')
    if 'mobile' in normalized or 'phone' in normalized:
        return 'mobile'
    if 'customer' in normalized and ('id' in normalized or 'number' in normalized or 'no' in normalized):
        return 'customer_number'
    if normalized == 'customerid' or normalized.startswith('customer id'):
        return 'customer_number'
    if 'card' in normalized and ('last4' in normalized or 'last 4' in normalized or 'digits' in normalized):
        return 'card_last4'
    return ''


def get_providers_by_category(category):
    """List providers synthesized from visible billers for the category."""
    norm = normalize_category_code(category)
    lookup_values = _category_lookup_values(category)
    cache_key = f'bbps:providers:{norm}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    category_filter = Q()
    for val in lookup_values:
        category_filter |= Q(biller_category__iexact=val)
    masters = BbpsBillerMaster.objects.filter(
        is_deleted=False,
        biller_status__in=ALLOWED_BILLER_STATUSES,
        is_active_local=True,
        soft_deleted_at__isnull=True,
    ).filter(category_filter).order_by('biller_name')
    if _stale_block_enabled():
        masters = masters.filter(is_stale=False)
    payload = [
        {
            'provider_id': m.pk,
            'provider_code': normalize_category_code(m.biller_id),
            'provider_name': m.biller_name,
            'provider_type': 'utility',
            'category': normalize_category_code(m.biller_category),
            'biller_options': [
                {
                    'map_id': m.pk,
                    'biller_id': m.biller_id,
                    'biller_name': m.biller_name,
                    'biller_category': m.biller_category,
                    'priority': 0,
                }
            ],
        }
        for m in masters
    ]
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
