"""Admin catalog visibility: cash-only apply, classification, and preview."""
from __future__ import annotations

from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.bbps.catalog.env import biller_master_qs_for_env
from apps.bbps.models import BbpsBillerMaster
from apps.bbps.services import (
    ALLOWED_BILLER_STATUSES,
    _biller_end_user_visible,
    _biller_supports_agt_cash,
    _channel_mode_limits_by_biller,
    _stale_block_enabled,
)
from apps.bbps.service_flow.catalog_ux_settings import is_cash_only_for_users
from apps.integrations.billavenue.registry import normalize_billavenue_mode


HOLD_ADMIN = 'admin'
HOLD_CASH_ONLY = 'cash_only'


def _norm_env(environment: str | None) -> str:
    raw = str(environment or '').strip().lower()
    return normalize_billavenue_mode(raw) if raw in ('uat', 'prod') else normalize_billavenue_mode(raw)


def _active_channel_codes(channel_limits) -> list[str]:
    return [
        str(c.payment_channel or '').strip().upper()
        for c in (channel_limits or [])
        if c.payment_channel
    ]


def _active_mode_labels(mode_limits) -> list[str]:
    return [str(m.payment_mode or '').strip() for m in (mode_limits or []) if m.payment_mode]


def classify_biller_partner_visibility(
    master: BbpsBillerMaster,
    *,
    channel_limits=None,
    mode_limits=None,
    cash_only: bool | None = None,
) -> dict[str, Any]:
    """Classify partner visibility and hidden reasons for admin directory DTOs."""
    if cash_only is None:
        cash_only = is_cash_only_for_users(getattr(master, 'environment', None))

    hold = str(getattr(master, 'local_visibility_hold', '') or '').strip()
    reasons: list[str] = []

    if master.soft_deleted_at:
        reasons.append('soft_deleted')

    if str(master.biller_status or '').strip().upper() not in ALLOWED_BILLER_STATUSES:
        reasons.append('inactive_status')

    if _stale_block_enabled() and bool(getattr(master, 'is_stale', False)):
        reasons.append('stale_mdm')

    ch_codes = _active_channel_codes(channel_limits)
    mode_labels = _active_mode_labels(mode_limits)

    cash_eligible = _biller_supports_agt_cash(
        master,
        channel_limits=channel_limits,
        mode_limits=mode_limits,
    )

    if cash_only:
        if 'AGT' not in ch_codes:
            reasons.append('no_agt_channel')
        if not cash_eligible:
            if 'no_cash_mode' not in reasons:
                reasons.append('no_cash_mode')

    if not mode_labels:
        reasons.append('no_payment_modes')

    if hold == HOLD_ADMIN or (not master.is_active_local and hold == HOLD_ADMIN):
        if 'admin_disabled' not in reasons:
            reasons.append('admin_disabled')
    elif hold == HOLD_CASH_ONLY:
        if 'cash_only_policy' not in reasons:
            reasons.append('cash_only_policy')
    elif not master.is_active_local:
        reasons.append('admin_disabled')

    partner_visible = bool(
        master.is_active_local
        and not master.soft_deleted_at
        and _biller_end_user_visible(
            master,
            cash_only=bool(cash_only),
            channel_limits=channel_limits,
            mode_limits=mode_limits,
        )
    )

    if not partner_visible and not reasons:
        reasons.append('provider_policy')

    return {
        'partner_visible': partner_visible,
        'cash_only_eligible': cash_eligible,
        'local_visibility_hold': hold,
        'hidden_reasons': sorted(set(reasons)) if not partner_visible else [],
        'payment_channels_summary': ', '.join(ch_codes) if ch_codes else '—',
        'payment_modes_summary': ', '.join(mode_labels[:6]) if mode_labels else '—',
    }


def _base_mdm_queryset(environment: str):
    qs = biller_master_qs_for_env(environment).filter(soft_deleted_at__isnull=True)
    return qs.prefetch_related('payment_channels', 'payment_modes')


def _limits_for_master(master: BbpsBillerMaster):
    channels = [
        c
        for c in master.payment_channels.all()
        if not c.is_deleted and c.is_active
    ]
    modes = [
        m
        for m in master.payment_modes.all()
        if not m.is_deleted and m.is_active
    ]
    return channels, modes


def apply_cash_only_visibility_for_env(environment: str | None = None) -> dict[str, int]:
    """
    When cash-only is ON: hide ineligible billers (except admin-held).
    When OFF: restore billers auto-hidden by cash-only policy only.
    """
    env = _norm_env(environment)
    cash_only = is_cash_only_for_users(env)
    now = timezone.now()
    hidden = 0
    restored = 0
    skipped_admin = 0
    unchanged = 0

    masters = list(_base_mdm_queryset(env))
    to_update: list[BbpsBillerMaster] = []

    for master in masters:
        hold = str(master.local_visibility_hold or '').strip()
        channels, modes = _limits_for_master(master)

        if cash_only:
            if hold == HOLD_ADMIN:
                skipped_admin += 1
                continue
            eligible = _biller_supports_agt_cash(
                master,
                channel_limits=channels,
                mode_limits=modes,
            ) and _biller_end_user_visible(
                master,
                cash_only=True,
                channel_limits=channels,
                mode_limits=modes,
            )
            if not eligible:
                if master.is_active_local or hold != HOLD_CASH_ONLY:
                    master.is_active_local = False
                    master.local_visibility_hold = HOLD_CASH_ONLY
                    master.updated_by_admin_at = now
                    to_update.append(master)
                    hidden += 1
                else:
                    unchanged += 1
            elif hold == HOLD_CASH_ONLY:
                master.is_active_local = True
                master.local_visibility_hold = ''
                master.updated_by_admin_at = now
                to_update.append(master)
                restored += 1
            else:
                unchanged += 1
        else:
            if hold == HOLD_CASH_ONLY:
                master.is_active_local = True
                master.local_visibility_hold = ''
                master.updated_by_admin_at = now
                to_update.append(master)
                restored += 1
            else:
                unchanged += 1

    if to_update:
        BbpsBillerMaster.objects.bulk_update(
            to_update,
            ['is_active_local', 'local_visibility_hold', 'updated_by_admin_at', 'updated_at'],
            batch_size=500,
        )

    return {
        'hidden': hidden,
        'restored': restored,
        'skipped_admin': skipped_admin,
        'unchanged': unchanged,
        'cash_only_for_users': bool(cash_only),
        'environment': env,
    }


def preview_cash_only_toggle(
    environment: str | None,
    *,
    cash_only_for_users: bool,
    sample_size: int = 10,
) -> dict[str, Any]:
    """Dry-run counts for enabling/disabling cash-only without DB writes."""
    env = _norm_env(environment)
    masters = list(_base_mdm_queryset(env))
    partner_visible = 0
    cash_only_eligible = 0
    would_hide: list[dict] = []
    would_restore = 0
    admin_hidden = 0
    cash_only_hidden = 0

    for master in masters:
        channels, modes = _limits_for_master(master)
        hold = str(master.local_visibility_hold or '').strip()
        classification = classify_biller_partner_visibility(
            master,
            channel_limits=channels,
            mode_limits=modes,
            cash_only=cash_only_for_users,
        )
        if classification['cash_only_eligible']:
            cash_only_eligible += 1
        if classification['partner_visible']:
            partner_visible += 1

        if hold == HOLD_ADMIN:
            admin_hidden += 1
        elif hold == HOLD_CASH_ONLY:
            cash_only_hidden += 1

        if cash_only_for_users:
            if hold == HOLD_ADMIN:
                continue
            eligible = classification['cash_only_eligible'] and _biller_end_user_visible(
                master,
                cash_only=True,
                channel_limits=channels,
                mode_limits=modes,
            )
            if not eligible and (master.is_active_local or hold != HOLD_CASH_ONLY):
                if len(would_hide) < sample_size:
                    would_hide.append(
                        {
                            'id': master.pk,
                            'biller_id': master.biller_id,
                            'biller_name': master.biller_name,
                            'biller_category': master.biller_category,
                            'hidden_reasons': classification['hidden_reasons'],
                        }
                    )
        else:
            if hold == HOLD_CASH_ONLY:
                would_restore += 1

    mdm_total = len(masters)
    would_hide_count = 0
    if cash_only_for_users:
        for master in masters:
            hold = str(master.local_visibility_hold or '').strip()
            if hold == HOLD_ADMIN:
                continue
            channels, modes = _limits_for_master(master)
            eligible = _biller_supports_agt_cash(
                master, channel_limits=channels, mode_limits=modes
            ) and _biller_end_user_visible(
                master, cash_only=True, channel_limits=channels, mode_limits=modes
            )
            if not eligible and (master.is_active_local or hold != HOLD_CASH_ONLY):
                would_hide_count += 1
    else:
        would_hide_count = 0

    return {
        'environment': env,
        'cash_only_for_users': bool(cash_only_for_users),
        'mdm_total': mdm_total,
        'partner_visible': partner_visible,
        'cash_only_eligible': cash_only_eligible,
        'admin_hidden': admin_hidden,
        'cash_only_hidden': cash_only_hidden,
        'would_hide_count': would_hide_count,
        'would_restore_count': would_restore,
        'sample_would_hide': would_hide,
    }


def catalog_visibility_summary(environment: str | None = None) -> dict[str, Any]:
    """Aggregate visibility stats for admin dashboard (SQL counts + cache)."""
    from django.core.cache import cache

    from apps.bbps.service_flow.catalog_ux_settings import get_catalog_ux_settings

    env = _norm_env(environment)
    cache_key = f'bbps:catalog_visibility_summary:{env}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    cash_only = is_cash_only_for_users(env)
    ux = get_catalog_ux_settings(env)
    qs = biller_master_qs_for_env(env).filter(soft_deleted_at__isnull=True)

    mdm_total = qs.count()
    partner_visible = qs.filter(
        is_active_local=True,
        biller_status__in=ALLOWED_BILLER_STATUSES,
    ).count()
    admin_hidden = qs.filter(local_visibility_hold=HOLD_ADMIN).count()
    cash_only_hidden = qs.filter(local_visibility_hold=HOLD_CASH_ONLY).count()
    hidden_from_partners = max(0, mdm_total - partner_visible)

    out = {
        'environment': env,
        'live_mode': env,
        'cash_only_for_users': bool(cash_only),
        'catalog_ux_updated_at': ux.get('updated_at'),
        'mdm_total': mdm_total,
        'partner_visible': partner_visible,
        'hidden_from_partners': hidden_from_partners,
        'admin_hidden': admin_hidden,
        'cash_only_hidden': cash_only_hidden,
        'cash_only_eligible': partner_visible,
    }
    cache.set(cache_key, out, timeout=60)
    return out


def hidden_billers_queryset(
    environment: str | None,
    *,
    reason: str | None = None,
    category: str | None = None,
    q: str | None = None,
):
    """SQL-filtered queryset for billers hidden from partner catalog."""
    env = _norm_env(environment)
    qs = _base_mdm_queryset(env).filter(
        Q(is_active_local=False) | Q(local_visibility_hold__in=[HOLD_ADMIN, HOLD_CASH_ONLY])
    )
    if category:
        qs = qs.filter(biller_category__icontains=category)
    if q:
        qs = qs.filter(Q(biller_name__icontains=q) | Q(biller_id__icontains=q))
    if reason == 'admin':
        qs = qs.filter(local_visibility_hold=HOLD_ADMIN)
    elif reason == 'cash_only':
        qs = qs.filter(local_visibility_hold=HOLD_CASH_ONLY)
    return qs.order_by('biller_name')


def invalidate_catalog_visibility_summary_cache(environment: str | None = None) -> None:
    from django.core.cache import cache

    if environment:
        cache.delete(f'bbps:catalog_visibility_summary:{_norm_env(environment)}')
    else:
        for env in ('uat', 'prod'):
            cache.delete(f'bbps:catalog_visibility_summary:{env}')


def iter_hidden_billers(
    environment: str | None,
    *,
    reason: str | None = None,
    category: str | None = None,
    q: str | None = None,
    cash_only: bool | None = None,
):
    """Yield hidden biller rows with classification for admin hidden list (page slice only)."""
    env = _norm_env(environment)
    if cash_only is None:
        cash_only = is_cash_only_for_users(env)

    qs = hidden_billers_queryset(env, reason=reason, category=category, q=q)

    for master in qs:
        channels, modes = _limits_for_master(master)
        classification = classify_biller_partner_visibility(
            master,
            channel_limits=channels,
            mode_limits=modes,
            cash_only=cash_only,
        )
        if classification['partner_visible']:
            continue
        if reason and reason not in ('admin', 'cash_only'):
            if reason not in classification['hidden_reasons']:
                continue
        yield master, classification


def assert_biller_can_be_enabled(master: BbpsBillerMaster) -> str | None:
    """Return error message if enable should be blocked; None if allowed."""
    env = getattr(master, 'environment', None)
    if not is_cash_only_for_users(env):
        return None
    channels, modes = _limits_for_master(master)
    if not _biller_supports_agt_cash(master, channel_limits=channels, mode_limits=modes):
        return (
            'Cannot enable biller while cash-only mode is active: '
            'biller lacks AGT channel and Cash payment mode.'
        )
    if not _biller_end_user_visible(
        master,
        cash_only=True,
        channel_limits=channels,
        mode_limits=modes,
    ):
        return (
            'Cannot enable biller while cash-only mode is active: '
            'biller is not eligible for partner catalog.'
        )
    return None
