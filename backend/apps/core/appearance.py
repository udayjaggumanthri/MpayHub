"""
Platform branding and theme configuration — singleton source of truth.
"""
from __future__ import annotations

from typing import Any

from django.core.cache import cache

CACHE_KEY = 'platform_appearance_status_v1'
CACHE_TTL_SECONDS = 8

DEFAULT_SITE_TITLE = 'mPayHub'
DEFAULT_LOGIN_WELCOME_HEADING = 'WELCOME TO'
DEFAULT_LOGIN_TAGLINE = 'Driven by trust, Built for Scale'


def get_config():
    """Load or create the singleton appearance config row."""
    from apps.core.models import PlatformAppearanceConfig

    config, _ = PlatformAppearanceConfig.objects.get_or_create(
        pk=PlatformAppearanceConfig.SINGLETON_PK,
        defaults={
            'site_title': DEFAULT_SITE_TITLE,
            'login_welcome_heading': DEFAULT_LOGIN_WELCOME_HEADING,
            'login_tagline': DEFAULT_LOGIN_TAGLINE,
            'default_theme': PlatformAppearanceConfig.THEME_LIGHT,
            'user_theme_toggle_enabled': False,
        },
    )
    return config


def invalidate_cache() -> None:
    cache.delete(f'{CACHE_KEY}_public')
    cache.delete(f'{CACHE_KEY}_admin')


def _logo_url(config, request=None) -> str | None:
    if not config.logo:
        return None
    try:
        url = config.logo.url
    except Exception:
        return None
    if request:
        return request.build_absolute_uri(url)
    return url


def _updated_by_dict(user) -> dict | None:
    if not user:
        return None
    return {
        'id': user.pk,
        'user_id': getattr(user, 'user_id', None),
        'name': f'{user.first_name or ""} {user.last_name or ""}'.strip()
        or str(user.phone or user.pk),
    }


def _build_status_dict(config, *, include_internal: bool = False, request=None) -> dict[str, Any]:
    out: dict[str, Any] = {
        'site_title': (config.site_title or '').strip() or DEFAULT_SITE_TITLE,
        'logo_url': _logo_url(config, request),
        'login_welcome_heading': (config.login_welcome_heading or '').strip() or DEFAULT_LOGIN_WELCOME_HEADING,
        'login_tagline': (config.login_tagline or '').strip() or DEFAULT_LOGIN_TAGLINE,
        'login_footer_note': (config.login_footer_note or '').strip(),
        'login_footer_privacy_url': (config.login_footer_privacy_url or '').strip(),
        'login_footer_terms_url': (config.login_footer_terms_url or '').strip(),
        'login_footer_refund_url': (config.login_footer_refund_url or '').strip(),
        'default_theme': config.default_theme or 'light',
        'user_theme_toggle_enabled': bool(config.user_theme_toggle_enabled),
        'updated_at': config.updated_at.isoformat() if config.updated_at else None,
    }

    if include_internal:
        out['has_logo'] = bool(config.logo)
        out['updated_by'] = _updated_by_dict(config.updated_by)

    return out


def get_status(*, include_internal: bool = False, use_cache: bool = True, request=None) -> dict[str, Any]:
    """Return branding and theme settings."""
    cache_suffix = '_admin' if include_internal else '_public'
    cache_key = f'{CACHE_KEY}{cache_suffix}'

    if use_cache and request is None:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    config = get_config()
    status = _build_status_dict(config, include_internal=include_internal, request=request)

    if use_cache and request is None:
        cache.set(cache_key, status, CACHE_TTL_SECONDS)

    return status


def update_config(*, changed_by, patch: dict, request=None) -> dict[str, Any]:
    """Apply admin patch to singleton config. Returns admin status dict."""
    config = get_config()

    text_fields = [
        'site_title',
        'login_welcome_heading',
        'login_tagline',
        'login_footer_note',
        'login_footer_privacy_url',
        'login_footer_terms_url',
        'login_footer_refund_url',
    ]
    update_fields = ['updated_at']

    for field in text_fields:
        if field in patch:
            setattr(config, field, patch.get(field) or '')
            update_fields.append(field)

    if 'default_theme' in patch:
        theme = patch.get('default_theme') or 'light'
        from apps.core.models import PlatformAppearanceConfig

        if theme not in {PlatformAppearanceConfig.THEME_LIGHT, PlatformAppearanceConfig.THEME_DARK}:
            theme = PlatformAppearanceConfig.THEME_LIGHT
        config.default_theme = theme
        update_fields.append('default_theme')

    if 'user_theme_toggle_enabled' in patch:
        config.user_theme_toggle_enabled = bool(patch['user_theme_toggle_enabled'])
        update_fields.append('user_theme_toggle_enabled')

    if patch.get('remove_logo'):
        if config.logo:
            config.logo.delete(save=False)
            config.logo = None
            update_fields.append('logo')
    elif 'logo' in patch and patch['logo'] is not None:
        if config.logo:
            config.logo.delete(save=False)
        config.logo = patch['logo']
        update_fields.append('logo')

    if changed_by is not None:
        config.updated_by = changed_by
        update_fields.append('updated_by')

    config.save(update_fields=list(dict.fromkeys(update_fields)))
    invalidate_cache()
    return get_status(include_internal=True, use_cache=False, request=request)
