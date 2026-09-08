"""
Central role helpers for mPayHub.

Platform operators (Super Admin, Admin) manage the portal but do not use agent
wallets. Channel roles form the commercial hierarchy.
"""
from __future__ import annotations

from typing import Any, Iterable

ROLE_SUPER_ADMIN = 'Super Admin'
ROLE_ADMIN = 'Admin'
ROLE_SUPER_DISTRIBUTOR = 'Super Distributor'
ROLE_MASTER_DISTRIBUTOR = 'Master Distributor'
ROLE_DISTRIBUTOR = 'Distributor'
ROLE_RETAILER = 'Retailer'

OPERATOR_ROLES: frozenset[str] = frozenset({ROLE_SUPER_ADMIN, ROLE_ADMIN})
CHANNEL_ROLES: frozenset[str] = frozenset(
    {
        ROLE_SUPER_DISTRIBUTOR,
        ROLE_MASTER_DISTRIBUTOR,
        ROLE_DISTRIBUTOR,
        ROLE_RETAILER,
    }
)

# Top → bottom including operators.
HIERARCHY_ROLE_ORDER: tuple[str, ...] = (
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_SUPER_DISTRIBUTOR,
    ROLE_MASTER_DISTRIBUTOR,
    ROLE_DISTRIBUTOR,
    ROLE_RETAILER,
)


def _role_of(user_or_role: Any) -> str:
    if user_or_role is None:
        return ''
    if isinstance(user_or_role, str):
        return user_or_role.strip()
    return (getattr(user_or_role, 'role', None) or '').strip()


def is_super_admin(user_or_role: Any) -> bool:
    return _role_of(user_or_role) == ROLE_SUPER_ADMIN


def is_admin(user_or_role: Any) -> bool:
    return _role_of(user_or_role) == ROLE_ADMIN


def is_platform_operator(user_or_role: Any) -> bool:
    """Admin or Super Admin — portal operators (not agent money flows)."""
    return _role_of(user_or_role) in OPERATOR_ROLES


def is_channel_role(user_or_role: Any) -> bool:
    return _role_of(user_or_role) in CHANNEL_ROLES
