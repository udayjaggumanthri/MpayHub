"""
Pay-in upline resolution (single source for hierarchy walks).
"""
from apps.users.models import UserHierarchy


def upline_chain(user):
    """
    Immediate parent first, then upward toward the top of the tree.
    Deterministic when multiple parent rows exist (oldest link first).
    """
    chain = []
    current = user
    seen = set()
    while current.id not in seen:
        seen.add(current.id)
        row = (
            UserHierarchy.objects.filter(child_user=current)
            .select_related('parent_user')
            .order_by('created_at', 'id')
            .first()
        )
        if not row:
            break
        chain.append(row.parent_user)
        current = row.parent_user
    return chain
