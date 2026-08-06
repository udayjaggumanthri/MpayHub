"""
Active BillAvenue environment helpers for env-scoped MDM catalog reads/writes.

Partners never pass env; admin activation chooses which catalog slice is live.
"""

from __future__ import annotations

from django.db.models import QuerySet

from apps.bbps.models import BbpsBillerMaster
from apps.integrations.billavenue.registry import get_active_billavenue_config, normalize_billavenue_mode


def active_bbps_environment() -> str:
    cfg = get_active_billavenue_config()
    if cfg and str(cfg.mode or '').lower() in ('uat', 'prod'):
        return normalize_billavenue_mode(cfg.mode)
    # Prefer any active (even disabled) uat/prod row for admin browsing hints.
    from apps.integrations.models import BillAvenueConfig

    active = (
        BillAvenueConfig.objects.filter(is_deleted=False, is_active=True, mode__in=['uat', 'prod'])
        .order_by('-updated_at')
        .first()
    )
    if active:
        return normalize_billavenue_mode(active.mode)
    return 'uat'


def catalog_counts_by_environment() -> dict[str, int]:
    from django.db.models import Count

    rows = (
        BbpsBillerMaster.objects.filter(is_deleted=False, soft_deleted_at__isnull=True)
        .values('environment')
        .annotate(c=Count('id'))
    )
    out = {'uat': 0, 'prod': 0}
    for r in rows:
        env = normalize_billavenue_mode(r.get('environment'))
        out[env] = int(r.get('c') or 0)
    return out


def biller_master_qs_for_env(environment: str | None = None) -> QuerySet[BbpsBillerMaster]:
    env = normalize_billavenue_mode(environment or active_bbps_environment())
    return BbpsBillerMaster.objects.filter(is_deleted=False, environment=env)


def get_biller_master(biller_id: str, *, environment: str | None = None) -> BbpsBillerMaster | None:
    bid = str(biller_id or '').strip()
    if not bid:
        return None
    return biller_master_qs_for_env(environment).filter(biller_id=bid).first()


def catalog_cache_env_key(environment: str | None = None) -> str:
    return normalize_billavenue_mode(environment or active_bbps_environment())
