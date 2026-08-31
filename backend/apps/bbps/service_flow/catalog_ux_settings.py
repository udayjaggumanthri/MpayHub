"""BBPS catalog UX settings (cash-only mode, etc.)."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from apps.bbps.catalog.env import active_bbps_environment
from apps.bbps.models import BbpsCatalogUxSettings
from apps.integrations.billavenue.registry import normalize_billavenue_mode


def _norm_env(environment: str | None = None) -> str:
    raw = str(environment or active_bbps_environment() or 'uat').strip().lower()
    return normalize_billavenue_mode(raw) if raw in ('uat', 'prod') else active_bbps_environment()


def get_or_create_catalog_ux_settings(environment: str | None = None) -> BbpsCatalogUxSettings:
    env = _norm_env(environment)
    row, _ = BbpsCatalogUxSettings.objects.get_or_create(
        environment=env,
        defaults={'cash_only_for_users': False},
    )
    return row


def serialize_catalog_ux_settings(row: BbpsCatalogUxSettings) -> dict[str, Any]:
    return {
        'environment': row.environment,
        'cash_only_for_users': bool(row.cash_only_for_users),
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def get_catalog_ux_settings(environment: str | None = None) -> dict[str, Any]:
    row = get_or_create_catalog_ux_settings(environment)
    return serialize_catalog_ux_settings(row)


def update_catalog_ux_settings(
    *,
    environment: str | None = None,
    cash_only_for_users: Optional[bool] = None,
    admin_user=None,
) -> dict[str, Any]:
    row = get_or_create_catalog_ux_settings(environment)
    if cash_only_for_users is not None:
        row.cash_only_for_users = bool(cash_only_for_users)
    if admin_user is not None:
        row.updated_by = admin_user
    row.save(update_fields=['cash_only_for_users', 'updated_by', 'updated_at'])
    _cached_cash_only_for_users.cache_clear()
    return serialize_catalog_ux_settings(row)


@lru_cache(maxsize=8)
def _cached_cash_only_for_users(env: str) -> bool:
    row = BbpsCatalogUxSettings.objects.filter(environment=env).only('cash_only_for_users').first()
    if row is None:
        # Create default row once; cache result afterward.
        row = get_or_create_catalog_ux_settings(env)
    return bool(row.cash_only_for_users)


def is_cash_only_for_users(environment: str | None = None) -> bool:
    env = _norm_env(environment)
    return _cached_cash_only_for_users(env)
