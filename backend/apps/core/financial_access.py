"""
Rules for which roles may move money (pay-in, payout, BBPS spend, wallet transfers).
"""
from rest_framework.exceptions import PermissionDenied

# Roles that may onboard and earn commission but must not initiate wallet movements.
FINANCIAL_TX_BLOCKED_ROLES = frozenset(
    {
        'Super Distributor',
    }
)


def user_may_perform_financial_txn(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', True):
        return False
    role = getattr(user, 'role', None) or ''
    return role not in FINANCIAL_TX_BLOCKED_ROLES


def assert_can_perform_financial_txn(user) -> None:
    """Raise PermissionDenied if this user must not perform pay-in, payout, BBPS payment, or transfers."""
    if user_may_perform_financial_txn(user):
        return
    raise PermissionDenied(
        'Your role cannot perform wallet transactions. Use the team and commission reports instead.'
    )
