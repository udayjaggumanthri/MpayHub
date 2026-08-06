"""
BillAvenue config registry: dual UAT/PROD rows, one active live config.

Runtime always resolves ``is_active=True``. Admin upserts by ``mode`` without
overwriting the sibling environment's secrets.
"""

from __future__ import annotations

from typing import Any

from apps.integrations.models import BillAvenueConfig

MODE_PRESETS: dict[str, dict[str, Any]] = {
    'uat': {
        'name': 'billavenue-uat',
        'mode': 'uat',
        'base_url': 'https://stgapi.billavenue.com',
    },
    'prod': {
        'name': 'billavenue-prod',
        'mode': 'prod',
        'base_url': 'https://api.billavenue.com',
    },
}


def normalize_billavenue_mode(mode: str | None) -> str:
    m = str(mode or '').strip().lower()
    return 'uat' if m == 'uat' else 'prod'


def get_active_billavenue_config() -> BillAvenueConfig | None:
    return BillAvenueConfig.objects.filter(
        is_deleted=False,
        enabled=True,
        is_active=True,
        mode__in=['uat', 'prod'],
    ).first()


def get_or_create_billavenue_mode_row(mode: str) -> BillAvenueConfig:
    """
    Return the config row for ``uat`` or ``prod``.

    Never clears secrets on an existing row. Creates an empty sibling with URL
    preset only when missing.
    """
    env = normalize_billavenue_mode(mode)
    preset = MODE_PRESETS[env]
    row = (
        BillAvenueConfig.objects.filter(mode=env, is_deleted=False)
        .order_by('-is_active', '-updated_at')
        .first()
    )
    if row:
        return row

    # Prefer renaming a uniquely named preset slot if somehow mode mismatched.
    by_name = BillAvenueConfig.objects.filter(name=preset['name'], is_deleted=False).first()
    if by_name:
        by_name.mode = env
        by_name.save(update_fields=['mode', 'updated_at'])
        return by_name

    return BillAvenueConfig.objects.create(
        name=preset['name'],
        mode=env,
        base_url=preset['base_url'],
        enabled=False,
        is_active=False,
    )


def environments_summary() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for env in ('uat', 'prod'):
        r = (
            BillAvenueConfig.objects.filter(mode=env, is_deleted=False)
            .order_by('-is_active', '-updated_at')
            .first()
        )
        out.append(
            {
                'mode': env,
                'configured': bool(
                    r
                    and (
                        (r.access_code or '').strip()
                        or (r.working_key_encrypted or '').strip()
                        or (r.base_url or '').strip()
                    )
                ),
                'is_active': bool(r and r.is_active),
                'enabled': bool(r and r.enabled),
                'has_working_key': bool(r and (r.working_key_encrypted or '').strip()),
                'has_iv': bool(r and (r.iv_encrypted or '').strip()),
                'working_key_length': len(r.get_working_key().strip()) if r and (r.working_key_encrypted or '').strip() else 0,
                'iv_length': len(r.get_iv().strip()) if r and (r.iv_encrypted or '').strip() else 0,
                'credentials_ready': billavenue_credentials_ready(r),
                'access_code_set': bool(r and (r.access_code or '').strip()),
                'institute_id': (r.institute_id if r else '') or '',
                'base_url': (r.base_url if r else '') or '',
                'id': r.pk if r else None,
            }
        )
    return out


def get_billavenue_config_for_mode(mode: str, *, require_enabled: bool = False) -> BillAvenueConfig | None:
    """Resolve the UAT or PROD config row without requiring it to be the live partner env."""
    env = normalize_billavenue_mode(mode)
    qs = BillAvenueConfig.objects.filter(mode=env, is_deleted=False)
    if require_enabled:
        qs = qs.filter(enabled=True)
    return qs.order_by('-is_active', '-updated_at').first()


def billavenue_credentials_missing(cfg: BillAvenueConfig | None) -> list[str]:
    """Return human-readable missing credential fields for operator messaging."""
    if not cfg:
        return ['config']
    missing: list[str] = []
    if not str(cfg.base_url or '').strip():
        missing.append('base_url')
    if not str(cfg.access_code or '').strip():
        missing.append('access_code')
    if not str(cfg.institute_id or '').strip():
        missing.append('institute_id')
    if not str(cfg.working_key_encrypted or '').strip():
        missing.append('working_key')
    elif len(str(cfg.get_working_key() or '').strip()) < 16:
        missing.append('working_key_invalid')
    if not str(cfg.iv_encrypted or '').strip():
        missing.append('iv')
    elif len(str(cfg.get_iv() or '').strip()) < 8:
        # Stored IV invalid; runtime uses BillAvenue PHP standard IV — prompt admin to fix.
        missing.append('iv_invalid')
    return missing


def billavenue_credentials_ready(cfg: BillAvenueConfig | None) -> bool:
    return not billavenue_credentials_missing(cfg)


def activate_billavenue_config(cfg: BillAvenueConfig, *, user=None) -> BillAvenueConfig:
    from django.utils import timezone

    BillAvenueConfig.objects.filter(is_deleted=False, is_active=True).exclude(pk=cfg.pk).update(
        is_active=False
    )
    cfg.is_active = True
    # Live row must be enabled so partner/runtime resolution (enabled+active) succeeds.
    cfg.enabled = True
    update_fields = ['is_active', 'enabled', 'updated_at']
    if cfg.activated_at is None:
        cfg.activated_at = timezone.now()
        update_fields.append('activated_at')
        if user is not None:
            cfg.activated_by = user
            update_fields.append('activated_by')
    cfg.save(update_fields=update_fields)
    return cfg
