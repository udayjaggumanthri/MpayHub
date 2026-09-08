"""
Module permission helpers (Phase B RBAC).
"""
from __future__ import annotations

from typing import Iterable

from django.core.cache import cache

from apps.core.models import AppModule, RoleModulePermission
from apps.core.roles import HIERARCHY_ROLE_ORDER, ROLE_SUPER_ADMIN, is_super_admin

# Seed catalog: mirrors frontend roleMenus keys + Super-Admin-only modules.
DEFAULT_MODULES: list[dict] = [
    {'code': 'dashboard', 'name': 'Dashboard', 'group': 'core', 'sort_order': 10},
    {'code': 'user_management', 'name': 'User Management', 'group': 'users', 'sort_order': 20},
    {'code': 'reports', 'name': 'Reports', 'group': 'reports', 'sort_order': 30},
    {'code': 'profile', 'name': 'Profile & Settings', 'group': 'core', 'sort_order': 40},
    {'code': 'announcements', 'name': 'Announcements', 'group': 'admin', 'sort_order': 50},
    {'code': 'maintenance', 'name': 'Maintenance mode', 'group': 'admin', 'sort_order': 60},
    {'code': 'appearance', 'name': 'Appearance & theme', 'group': 'admin', 'sort_order': 70},
    {'code': 'wallet_adjustments', 'name': 'Wallet Adjustments', 'group': 'admin', 'sort_order': 80},
    {'code': 'pay_in_setup', 'name': 'Pay-in setup', 'group': 'admin', 'sort_order': 90},
    {'code': 'manual_qr', 'name': 'Manual QR', 'group': 'admin', 'sort_order': 100},
    {'code': 'notifications', 'name': 'Notifications', 'group': 'admin', 'sort_order': 110},
    {'code': 'bbps_console', 'name': 'BBPS Console', 'group': 'admin', 'sort_order': 120},
    {'code': 'aeps', 'name': 'AEPS', 'group': 'products', 'sort_order': 130},
    {'code': 'fund_management', 'name': 'Fund Management', 'group': 'products', 'sort_order': 140},
    {'code': 'bbps', 'name': 'BBPS', 'group': 'products', 'sort_order': 150},
    {'code': 'roles_permissions', 'name': 'Roles & permissions', 'group': 'super', 'sort_order': 200},
    {'code': 'test_usage', 'name': 'Test usage mode', 'group': 'super', 'sort_order': 210},
]

# Role → enabled module codes (seed from current menus).
DEFAULT_ROLE_MODULES: dict[str, list[str]] = {
    ROLE_SUPER_ADMIN: [m['code'] for m in DEFAULT_MODULES],
    'Admin': [
        'dashboard',
        'user_management',
        'reports',
        'profile',
        'announcements',
        'maintenance',
        'appearance',
        'wallet_adjustments',
        'pay_in_setup',
        'manual_qr',
        'notifications',
        'bbps_console',
        'aeps',
        'roles_permissions',  # view-only in UI; edit gated separately
    ],
    'Super Distributor': [
        'dashboard',
        'aeps',
        'user_management',
        'fund_management',
        'bbps',
        'reports',
        'profile',
    ],
    'Master Distributor': [
        'dashboard',
        'aeps',
        'user_management',
        'fund_management',
        'bbps',
        'reports',
        'profile',
    ],
    'Distributor': [
        'dashboard',
        'aeps',
        'user_management',
        'fund_management',
        'bbps',
        'reports',
        'profile',
    ],
    'Retailer': [
        'dashboard',
        'aeps',
        'fund_management',
        'bbps',
        'reports',
        'profile',
    ],
}

CACHE_KEY = 'rbac:role_modules:{role}'


def _cache_key_for_role(role: str) -> str:
    # Memcached-safe: no spaces
    return CACHE_KEY.format(role=(role or '').replace(' ', '_'))


def seed_modules_and_permissions(*, reset: bool = False) -> dict:
    """Idempotent seed of AppModule + RoleModulePermission from DEFAULT_*."""
    created_modules = 0
    for row in DEFAULT_MODULES:
        obj, created = AppModule.objects.update_or_create(
            code=row['code'],
            defaults={
                'name': row['name'],
                'group': row['group'],
                'sort_order': row['sort_order'],
                'is_active': True,
            },
        )
        if created:
            created_modules += 1

    created_perms = 0
    updated_perms = 0
    for role, codes in DEFAULT_ROLE_MODULES.items():
        code_set = set(codes)
        for mod in DEFAULT_MODULES:
            enabled = mod['code'] in code_set
            obj, created = RoleModulePermission.objects.get_or_create(
                role=role,
                module_code=mod['code'],
                defaults={'enabled': enabled},
            )
            if created:
                created_perms += 1
            elif reset and obj.enabled != enabled:
                obj.enabled = enabled
                obj.save(update_fields=['enabled'])
                updated_perms += 1
        cache.delete(_cache_key_for_role(role))

    return {
        'modules_created': created_modules,
        'permissions_created': created_perms,
        'permissions_updated': updated_perms,
    }


def enabled_modules_for_role(role: str | None) -> list[str]:
    role = (role or '').strip()
    if not role:
        return []
    if role == ROLE_SUPER_ADMIN:
        return list(AppModule.objects.filter(is_active=True).order_by('sort_order').values_list('code', flat=True)) or [
            m['code'] for m in DEFAULT_MODULES
        ]

    cache_key = _cache_key_for_role(role)
    cached = cache.get(cache_key)
    if cached is not None:
        return list(cached)

    codes = list(
        RoleModulePermission.objects.filter(role=role, enabled=True).values_list(
            'module_code', flat=True
        )
    )
    cache.set(cache_key, codes, timeout=120)
    return codes


def has_module(user, code: str) -> bool:
    if is_super_admin(user):
        return True
    role = getattr(user, 'role', None)
    return code in enabled_modules_for_role(role)


def permissions_payload_for_user(user) -> dict:
    role = getattr(user, 'role', None)
    modules = enabled_modules_for_role(role)
    return {
        'role': role,
        'modules': modules,
        'is_super_admin': is_super_admin(user),
    }


def matrix_snapshot() -> dict:
    modules = list(
        AppModule.objects.filter(is_active=True).order_by('sort_order').values(
            'code', 'name', 'group', 'sort_order'
        )
    )
    perms = {}
    for row in RoleModulePermission.objects.all().values('role', 'module_code', 'enabled'):
        perms.setdefault(row['role'], {})[row['module_code']] = bool(row['enabled'])
    return {
        'roles': list(HIERARCHY_ROLE_ORDER),
        'modules': modules,
        'permissions': perms,
    }


def set_role_module_enabled(*, actor, role: str, module_code: str, enabled: bool) -> None:
    if not is_super_admin(actor):
        raise ValueError('Only Super Admin may edit role permissions.')
    role = (role or '').strip()
    module_code = (module_code or '').strip()
    if role not in HIERARCHY_ROLE_ORDER:
        raise ValueError('Invalid role.')
    if not AppModule.objects.filter(code=module_code, is_active=True).exists():
        raise ValueError('Invalid module.')
    RoleModulePermission.objects.update_or_create(
        role=role,
        module_code=module_code,
        defaults={'enabled': bool(enabled)},
    )
    cache.delete(_cache_key_for_role(role))
