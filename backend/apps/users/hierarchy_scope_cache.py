"""Cache invalidation for hierarchy-scoped user ID sets."""
from __future__ import annotations

from django.core.cache import cache

from apps.users.models import UserHierarchy

VIEWABLE_IDS_CACHE_TTL = 60
VIEWABLE_IDS_KEY_PREFIX = 'users:viewable_ids:'
TEAM_TXN_IDS_KEY_PREFIX = 'users:team_txn_ids:'


def viewable_user_ids_cache_key(user_pk: int) -> str:
    return f'{VIEWABLE_IDS_KEY_PREFIX}{user_pk}'


def _ancestor_user_ids(user_pk: int) -> set[int]:
    """All users who may have this user in their downline view (walk up the tree)."""
    seen: set[int] = {user_pk}
    frontier = {user_pk}
    while frontier:
        parent_ids = set(
            UserHierarchy.objects.filter(child_user_id__in=frontier).values_list('parent_user_id', flat=True)
        )
        parent_ids -= seen
        if not parent_ids:
            break
        seen |= parent_ids
        frontier = parent_ids
    return seen


def invalidate_hierarchy_scope_cache(parent_user_id: int, child_user_id: int) -> None:
    """Clear cached viewable/team ID sets for users affected by a hierarchy edge change."""
    affected = _ancestor_user_ids(parent_user_id) | _ancestor_user_ids(child_user_id)
    affected.add(int(parent_user_id))
    affected.add(int(child_user_id))
    for pk in affected:
        cache.delete(viewable_user_ids_cache_key(pk))
        cache.delete(f'{TEAM_TXN_IDS_KEY_PREFIX}{pk}')
