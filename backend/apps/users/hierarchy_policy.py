"""
Hierarchy onboarding policy — single source of truth for who may create/manage which roles.

View/list/edit access for existing users uses ``UserHierarchy.get_subordinates()`` (tree-based).
This module governs direct onboarding (create) and role-change validation only.
"""
from __future__ import annotations

from typing import Any, FrozenSet

from apps.core.roles import (
    CHANNEL_ROLES,
    HIERARCHY_ROLE_ORDER,
    ROLE_ADMIN,
    ROLE_DISTRIBUTOR,
    ROLE_MASTER_DISTRIBUTOR,
    ROLE_RETAILER,
    ROLE_SUPER_ADMIN,
    ROLE_SUPER_DISTRIBUTOR,
    is_platform_operator,
    is_super_admin,
)

# Re-export order for callers that imported from this module.
__all__ = [
    'HIERARCHY_ROLE_ORDER',
    'CREATABLE_CHILD_ROLES',
    'creatable_roles_for',
    'can_parent_create_child',
    'manageable_roles_for',
    'assignable_roles_for_change',
    'assignable_roles_for_admin_change',
    'policy_snapshot',
]

# Roles each parent role may onboard as direct reports.
CREATABLE_CHILD_ROLES: dict[str, FrozenSet[str]] = {
    ROLE_SUPER_ADMIN: frozenset(
        {
            ROLE_SUPER_ADMIN,
            ROLE_ADMIN,
            ROLE_SUPER_DISTRIBUTOR,
            ROLE_MASTER_DISTRIBUTOR,
            ROLE_DISTRIBUTOR,
            ROLE_RETAILER,
        }
    ),
    ROLE_ADMIN: frozenset(
        {
            ROLE_SUPER_DISTRIBUTOR,
            ROLE_MASTER_DISTRIBUTOR,
            ROLE_DISTRIBUTOR,
            ROLE_RETAILER,
        }
    ),
    ROLE_SUPER_DISTRIBUTOR: frozenset(
        {
            ROLE_MASTER_DISTRIBUTOR,
            ROLE_DISTRIBUTOR,
            ROLE_RETAILER,
        }
    ),
    ROLE_MASTER_DISTRIBUTOR: frozenset(
        {
            ROLE_DISTRIBUTOR,
            ROLE_RETAILER,
        }
    ),
    ROLE_DISTRIBUTOR: frozenset(
        {
            ROLE_RETAILER,
        }
    ),
    ROLE_RETAILER: frozenset(),
}


def creatable_roles_for(parent_role: str | None) -> list[str]:
    """Return creatable child roles for a parent role, in hierarchy order."""
    allowed = CREATABLE_CHILD_ROLES.get((parent_role or '').strip(), frozenset())
    return [role for role in HIERARCHY_ROLE_ORDER if role in allowed]


def can_parent_create_child(parent_role: str | None, child_role: str | None) -> bool:
    """True if parent_role may onboard a direct report with child_role."""
    if not parent_role or not child_role:
        return False
    return child_role in CREATABLE_CHILD_ROLES.get(parent_role.strip(), frozenset())


def manageable_roles_for(parent_role: str | None) -> list[str]:
    """Alias for creatable_roles_for — roles this parent may manage via onboarding."""
    return creatable_roles_for(parent_role)


def assignable_roles_for_change(actor: Any = None) -> list[str]:
    """
    Roles the actor may assign via profile promote/demote.

    Super Admin: Super Admin + Admin + channel.
    Admin: channel roles only (cannot promote to Admin or Super Admin).
    """
    if is_super_admin(actor):
        return list(HIERARCHY_ROLE_ORDER)
    if is_platform_operator(actor) or (isinstance(actor, str) and actor == ROLE_ADMIN):
        # Admin actor — channel only
        return [r for r in HIERARCHY_ROLE_ORDER if r in CHANNEL_ROLES]
    # Legacy no-arg call: treat as Admin (channel-only) — safer than including Admin
    if actor is None:
        return [r for r in HIERARCHY_ROLE_ORDER if r in CHANNEL_ROLES]
    return creatable_roles_for(getattr(actor, 'role', None) if not isinstance(actor, str) else actor)


def assignable_roles_for_admin_change() -> list[str]:
    """
    Deprecated alias — returns channel roles only (Admin-safe list).

    Prefer ``assignable_roles_for_change(actor)``.
    """
    return [r for r in HIERARCHY_ROLE_ORDER if r in CHANNEL_ROLES]


def policy_snapshot() -> dict[str, list[str]]:
    """Serializable matrix for API clients."""
    return {role: creatable_roles_for(role) for role in HIERARCHY_ROLE_ORDER}
