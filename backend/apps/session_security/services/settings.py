"""Session security settings accessor (cached singleton)."""
from __future__ import annotations

from django.core.cache import cache

from apps.session_security.constants import (
    CACHE_SETTINGS_KEY,
    CACHE_SETTINGS_TTL,
    IDLE_TIMEOUT_DEFAULT,
    IDLE_TIMEOUT_MAX,
    IDLE_TIMEOUT_MIN,
)
from apps.session_security.models import SessionSecuritySettings


def invalidate_settings_cache() -> None:
    cache.delete(CACHE_SETTINGS_KEY)


def get_settings() -> SessionSecuritySettings:
    cached = cache.get(CACHE_SETTINGS_KEY)
    if cached is not None:
        return cached

    config, _ = SessionSecuritySettings.objects.get_or_create(
        pk=SessionSecuritySettings.SINGLETON_PK,
        defaults={
            'ip_location_enforcement_enabled': True,
            'audit_logging_enabled': True,
            'single_session_enforcement_enabled': True,
            'idle_timeout_minutes': IDLE_TIMEOUT_DEFAULT,
        },
    )
    cache.set(CACHE_SETTINGS_KEY, config, CACHE_SETTINGS_TTL)
    return config


def clamp_idle_timeout(minutes: int) -> int:
    try:
        value = int(minutes)
    except (TypeError, ValueError):
        return IDLE_TIMEOUT_DEFAULT
    return max(IDLE_TIMEOUT_MIN, min(IDLE_TIMEOUT_MAX, value))


def update_settings(*, changed_by=None, **patch) -> SessionSecuritySettings:
    config = get_settings()
    fields = []
    if 'ip_location_enforcement_enabled' in patch:
        config.ip_location_enforcement_enabled = bool(patch['ip_location_enforcement_enabled'])
        fields.append('ip_location_enforcement_enabled')
    if 'audit_logging_enabled' in patch:
        config.audit_logging_enabled = bool(patch['audit_logging_enabled'])
        fields.append('audit_logging_enabled')
    if 'single_session_enforcement_enabled' in patch:
        config.single_session_enforcement_enabled = bool(
            patch['single_session_enforcement_enabled']
        )
        fields.append('single_session_enforcement_enabled')
    if 'idle_timeout_minutes' in patch:
        config.idle_timeout_minutes = clamp_idle_timeout(patch['idle_timeout_minutes'])
        fields.append('idle_timeout_minutes')
    if changed_by is not None:
        config.updated_by = changed_by
        fields.append('updated_by')
    if fields:
        fields.append('updated_at')
        config.save(update_fields=fields)
    invalidate_settings_cache()
    return get_settings()


def settings_to_dict(config: SessionSecuritySettings | None = None) -> dict:
    config = config or get_settings()
    updated_by = None
    if config.updated_by_id:
        u = config.updated_by
        updated_by = {
            'id': u.id,
            'display_code': getattr(u, 'display_code', None) or getattr(u, 'user_id', None),
            'phone': u.phone,
            'full_name': u.get_full_name() or '',
        }
    return {
        'ip_location_enforcement_enabled': bool(config.ip_location_enforcement_enabled),
        'audit_logging_enabled': bool(config.audit_logging_enabled),
        'single_session_enforcement_enabled': bool(config.single_session_enforcement_enabled),
        'idle_timeout_minutes': int(config.idle_timeout_minutes),
        'idle_timeout_min': IDLE_TIMEOUT_MIN,
        'idle_timeout_max': IDLE_TIMEOUT_MAX,
        'updated_at': config.updated_at.isoformat() if config.updated_at else None,
        'updated_by': updated_by,
    }
