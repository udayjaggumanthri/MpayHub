"""Admin biller directory queryset helpers."""
from __future__ import annotations

from django.db.models import Q

from apps.bbps.catalog.env import active_bbps_environment, biller_master_qs_for_env
from apps.bbps.service_flow.catalog_visibility import (
    HOLD_ADMIN,
    HOLD_CASH_ONLY,
    classify_biller_partner_visibility,
)
from apps.bbps.service_flow.catalog_ux_settings import is_cash_only_for_users
from apps.integrations.billavenue.registry import normalize_billavenue_mode


def resolve_catalog_env(request, *, default_live: bool = True) -> str:
    live_mode = active_bbps_environment()
    env_param = str(
        request.query_params.get('environment')
        or request.query_params.get('mode')
        or ''
    ).strip().lower()
    if env_param in ('uat', 'prod'):
        return normalize_billavenue_mode(env_param)
    return live_mode if default_live else 'uat'


def admin_biller_directory_queryset(
    *,
    catalog_env: str,
    category: str | None = None,
    q: str | None = None,
    active: str | None = None,
    hold: str | None = None,
    cash_only_eligible: str | None = None,
    view: str = 'mdm',
):
    qs = (
        biller_master_qs_for_env(catalog_env)
        .filter(soft_deleted_at__isnull=True)
        .prefetch_related('payment_channels', 'payment_modes')
        .order_by('biller_name')
    )
    if category:
        qs = qs.filter(biller_category__icontains=category)
    if q:
        qs = qs.filter(Q(biller_name__icontains=q) | Q(biller_id__icontains=q))
    if active in ('true', 'false'):
        qs = qs.filter(is_active_local=(active == 'true'))
    if hold == 'admin':
        qs = qs.filter(local_visibility_hold=HOLD_ADMIN)
    elif hold == 'cash_only':
        qs = qs.filter(local_visibility_hold=HOLD_CASH_ONLY)
    if view == 'partner':
        qs = qs.filter(is_active_local=True)
    return qs


def filter_partner_visible_masters(
    masters: list,
    *,
    catalog_env: str,
    cash_only_eligible: str | None = None,
) -> list:
    """Post-filter masters for partner view using batched classification."""
    cash_only = is_cash_only_for_users(catalog_env)
    visible = []
    for master in masters:
        channels = [
            c for c in master.payment_channels.all() if not c.is_deleted and c.is_active
        ]
        modes = [
            m for m in master.payment_modes.all() if not m.is_deleted and m.is_active
        ]
        info = classify_biller_partner_visibility(
            master,
            channel_limits=channels,
            mode_limits=modes,
            cash_only=cash_only,
        )
        if not info['partner_visible']:
            continue
        if cash_only_eligible == 'true' and not info['cash_only_eligible']:
            continue
        if cash_only_eligible == 'false' and info['cash_only_eligible']:
            continue
        visible.append((master, info))
    return visible


def paginate_partner_visible(
    qs,
    *,
    page: int,
    page_size: int,
    catalog_env: str,
    cash_only_eligible: str | None = None,
) -> tuple[list, int]:
    """Scan queryset and return paginated partner-visible masters."""
    all_masters = list(qs)
    visible_pairs = filter_partner_visible_masters(
        all_masters,
        catalog_env=catalog_env,
        cash_only_eligible=cash_only_eligible,
    )
    total = len(visible_pairs)
    start = (page - 1) * page_size
    end = start + page_size
    return visible_pairs[start:end], total
