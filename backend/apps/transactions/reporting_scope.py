"""
Query helpers for self vs downline (team) reporting.
"""
from __future__ import annotations

from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.authentication.models import User
from apps.users.models import UserHierarchy

TEAM_SCOPE_ROLES = frozenset(
    {
        'Admin',
        'Super Distributor',
        'Master Distributor',
        'Distributor',
    }
)


def get_report_scope(request) -> str:
    raw = (request.query_params.get('scope') or 'self').strip().lower()
    return raw if raw in ('self', 'team') else 'self'


def team_transaction_user_ids(viewer: User) -> frozenset[int]:
    """
    User PKs whose activity is visible in *team* scope for Transaction / PassbookEntry.

    - Super Distributor / Admin: self + full downline tree (Admin handled separately via Q()).
    - Master Distributor: self + Distributor + Retailer in subtree.
    - Distributor: self + Retailer downline only.
    """
    role = getattr(viewer, 'role', None) or ''
    base = {viewer.pk}
    subs = UserHierarchy.get_subordinates(viewer)
    if role == 'Super Distributor':
        return frozenset(base | {s.pk for s in subs})
    if role == 'Master Distributor':
        return frozenset(
            base | {s.pk for s in subs if getattr(s, 'role', '') in ('Distributor', 'Retailer')}
        )
    if role == 'Distributor':
        return frozenset(base | {s.pk for s in subs if getattr(s, 'role', '') == 'Retailer'})
    if role == 'Admin':
        # Not used — caller uses Q() for all users.
        return frozenset()
    return frozenset(base)


def commission_team_source_user_ids(viewer: User) -> list[int] | None:
    """
    For CommissionLedger team rows: meta.source_user_id must be in this list.
    None = Admin (no extra constraint).
    """
    role = getattr(viewer, 'role', None) or ''
    if role == 'Admin':
        return None
    subs = UserHierarchy.get_subordinates(viewer)
    if role == 'Super Distributor':
        return [s.pk for s in subs]
    if role == 'Master Distributor':
        return [s.pk for s in subs if getattr(s, 'role', '') in ('Distributor', 'Retailer')]
    if role == 'Distributor':
        return [s.pk for s in subs if getattr(s, 'role', '') == 'Retailer']
    return []


def transaction_user_q(request) -> Q:
    """Filter Transaction / PassbookEntry by owner; team uses role-scoped downline sets."""
    scope = get_report_scope(request)
    user = request.user
    if scope == 'self':
        return Q(user=user)
    role = getattr(user, 'role', None)
    if role not in TEAM_SCOPE_ROLES:
        raise PermissionDenied('Team report scope is not enabled for your role.')
    if role == 'Admin':
        return Q()
    ids = team_transaction_user_ids(user)
    if not ids:
        return Q(pk__in=[])
    return Q(user_id__in=ids)


def commission_ledger_q_for_team(request) -> Q:
    """
    Extra filter on CommissionLedger (recipient is always request.user).
    Team = only pay-in commissions attributed to a subordinate in meta.source_user_id,
    scoped by distributor / MD / SD rules.
    """
    scope = get_report_scope(request)
    if scope == 'self':
        return Q()
    user = request.user
    role = getattr(user, 'role', None)
    if role not in TEAM_SCOPE_ROLES:
        raise PermissionDenied('Team report scope is not enabled for your role.')
    if role == 'Admin':
        return Q()
    ids = commission_team_source_user_ids(user)
    if ids is None:
        return Q()
    if not ids:
        return Q(pk__in=[])
    return Q(meta__source_user_id__in=ids)


def is_direct_subordinate(manager: User, subject: User) -> bool:
    """True if subject is an immediate child of manager in UserHierarchy."""
    if not manager or not subject:
        return False
    return UserHierarchy.objects.filter(parent_user=manager, child_user=subject).exists()
