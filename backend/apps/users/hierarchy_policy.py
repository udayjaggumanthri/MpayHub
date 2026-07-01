"""
Hierarchy onboarding policy — single source of truth for who may create/manage which roles.

View/list/edit access for existing users uses ``UserHierarchy.get_subordinates()`` (tree-based).
This module governs direct onboarding (create) and role-change validation only.
"""
from __future__ import annotations

from typing import FrozenSet

# Ordered from top to bottom of the commercial hierarchy.
HIERARCHY_ROLE_ORDER: tuple[str, ...] = (
    'Admin',
    'Super Distributor',
    'Master Distributor',
    'Distributor',
    'Retailer',
)

# Roles each parent role may onboard as direct reports.
CREATABLE_CHILD_ROLES: dict[str, FrozenSet[str]] = {
    'Admin': frozenset({
        'Super Distributor',
        'Master Distributor',
        'Distributor',
        'Retailer',
    }),
    'Super Distributor': frozenset({
        'Master Distributor',
        'Distributor',
        'Retailer',
    }),
    'Master Distributor': frozenset({
        'Distributor',
        'Retailer',
    }),
    'Distributor': frozenset({
        'Retailer',
    }),
    'Retailer': frozenset(),
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


def policy_snapshot() -> dict[str, list[str]]:
    """Serializable matrix for API clients."""
    return {role: creatable_roles_for(role) for role in HIERARCHY_ROLE_ORDER}
