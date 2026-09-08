"""
Portal test-usage mode helpers.
"""
from __future__ import annotations

from apps.core.models import PortalAccessConfig
from apps.core.roles import is_super_admin

ACCESS_CODE_TEST_USAGE_MODE = 'TEST_USAGE_MODE'

DEFAULT_TEST_USAGE_TITLE = 'Test usage mode'
DEFAULT_TEST_USAGE_MESSAGE = (
    'The portal is currently in test usage mode. Contact your administrator.'
)


def get_portal_access_config() -> PortalAccessConfig:
    cfg, _ = PortalAccessConfig.objects.get_or_create(
        pk=PortalAccessConfig.SINGLETON_PK,
        defaults={
            'test_usage_mode_enabled': False,
            'test_usage_title': DEFAULT_TEST_USAGE_TITLE,
            'test_usage_message': DEFAULT_TEST_USAGE_MESSAGE,
        },
    )
    return cfg


def portal_access_status(*, include_internal: bool = False) -> dict:
    cfg = get_portal_access_config()
    data = {
        'test_usage_mode_enabled': bool(cfg.test_usage_mode_enabled),
        'test_usage_title': cfg.test_usage_title or DEFAULT_TEST_USAGE_TITLE,
        'test_usage_message': cfg.test_usage_message or DEFAULT_TEST_USAGE_MESSAGE,
        'updated_at': cfg.updated_at.isoformat() if cfg.updated_at else None,
    }
    if include_internal and cfg.updated_by_id:
        data['updated_by'] = {
            'id': cfg.updated_by_id,
            'display_code': getattr(cfg.updated_by, 'display_code', None),
            'email': getattr(cfg.updated_by, 'email', None),
        }
    elif include_internal:
        data['updated_by'] = None
    return data


def update_portal_access(*, changed_by, patch: dict) -> dict:
    cfg = get_portal_access_config()
    if 'test_usage_mode_enabled' in patch:
        cfg.test_usage_mode_enabled = bool(patch['test_usage_mode_enabled'])
    if 'test_usage_title' in patch:
        cfg.test_usage_title = str(patch['test_usage_title'] or '')[:200]
    if 'test_usage_message' in patch:
        cfg.test_usage_message = str(patch['test_usage_message'] or '')
    cfg.updated_by = changed_by
    cfg.save()
    return portal_access_status(include_internal=True)


def user_may_login_under_test_mode(user) -> bool:
    """
    Super Admin always allowed (break-glass).
    When mode is off → everyone who otherwise may login.
    When mode is on → Super Admin or is_test_user.
    """
    cfg = get_portal_access_config()
    if not cfg.test_usage_mode_enabled:
        return True
    if is_super_admin(user):
        return True
    return bool(getattr(user, 'is_test_user', False))


def test_usage_block_detail() -> dict:
    cfg = get_portal_access_config()
    return {
        'code': ACCESS_CODE_TEST_USAGE_MODE,
        'title': cfg.test_usage_title or DEFAULT_TEST_USAGE_TITLE,
        'message': cfg.test_usage_message or DEFAULT_TEST_USAGE_MESSAGE,
    }
