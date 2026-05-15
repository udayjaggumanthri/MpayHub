"""
Per-user and per-role rules for login, pay-in, and payment outflows.

Single source of truth for fund_management, BBPS, wallets, and auth layers.
"""
from __future__ import annotations

from typing import Any

from rest_framework.exceptions import PermissionDenied

# Roles that may onboard and earn commission but must not initiate wallet movements.
FINANCIAL_TX_BLOCKED_ROLES = frozenset(
    {
        'Admin',
        'Super Distributor',
    }
)

ACCESS_CODE_ROLE_FINANCIAL_BLOCKED = 'ROLE_FINANCIAL_BLOCKED'
ACCESS_CODE_USER_DISABLED = 'USER_DISABLED'
ACCESS_CODE_USER_RESTRICTED = 'USER_RESTRICTED'
ACCESS_CODE_USER_PAYMENTS_LOCKED = 'USER_PAYMENTS_LOCKED'


def _role_may_use_financial_apis(user) -> bool:
    if not user or not getattr(user, 'is_authenticated', True):
        return False
    role = getattr(user, 'role', None) or ''
    return role not in FINANCIAL_TX_BLOCKED_ROLES


def user_may_login(user) -> bool:
    """May obtain/refresh API session (active account or pay-in-only disabled exception)."""
    if not user or not getattr(user, 'is_authenticated', True):
        return False
    if bool(getattr(user, 'is_active', True)):
        return True
    return bool(getattr(user, 'pay_in_allowed_when_disabled', False))


def user_may_pay_in(user) -> bool:
    """May use pay-in / load-money APIs."""
    if not _role_may_use_financial_apis(user):
        return False
    if not user_may_login(user):
        return False
    if bool(getattr(user, 'is_restricted', False)):
        return False
    return True


def user_may_pay_out(user) -> bool:
    """May use BBPS bill pay, payout, and wallet transfer outflows."""
    if not _role_may_use_financial_apis(user):
        return False
    if not bool(getattr(user, 'is_active', True)):
        return False
    if bool(getattr(user, 'is_restricted', False)):
        return False
    if bool(getattr(user, 'payments_locked', False)):
        return False
    return True


def user_may_perform_financial_txn(user) -> bool:
    """Legacy combined check: both pay-in and pay-out allowed."""
    return user_may_pay_in(user) and user_may_pay_out(user)


def _permission_denied(code: str, message: str) -> PermissionDenied:
    return PermissionDenied(detail={'code': code, 'message': message})


def assert_can_login(user) -> None:
    if user_may_login(user):
        return
    raise _permission_denied(
        ACCESS_CODE_USER_DISABLED,
        'Your account is disabled. Contact your administrator.',
    )


def assert_can_pay_in(user) -> None:
    if not _role_may_use_financial_apis(user):
        raise _permission_denied(
            ACCESS_CODE_ROLE_FINANCIAL_BLOCKED,
            'Your role cannot perform wallet transactions. Use the team and commission reports instead.',
        )
    if not user_may_login(user):
        raise _permission_denied(
            ACCESS_CODE_USER_DISABLED,
            'Your account is disabled. Contact your administrator.',
        )
    if bool(getattr(user, 'is_restricted', False)):
        raise _permission_denied(
            ACCESS_CODE_USER_RESTRICTED,
            'Your account is restricted to read-only access. Pay-in is not available.',
        )


def assert_can_pay_out(user) -> None:
    if not _role_may_use_financial_apis(user):
        raise _permission_denied(
            ACCESS_CODE_ROLE_FINANCIAL_BLOCKED,
            'Your role cannot perform wallet transactions. Use the team and commission reports instead.',
        )
    if not bool(getattr(user, 'is_active', True)):
        raise _permission_denied(
            ACCESS_CODE_USER_DISABLED,
            'Your account is disabled. Payment outflows are not available.',
        )
    if bool(getattr(user, 'is_restricted', False)):
        raise _permission_denied(
            ACCESS_CODE_USER_RESTRICTED,
            'Your account is restricted to read-only access. Payments are not available.',
        )
    if bool(getattr(user, 'payments_locked', False)):
        raise _permission_denied(
            ACCESS_CODE_USER_PAYMENTS_LOCKED,
            'Payments are locked on your account. Pay-in and reports may still be available.',
        )


def assert_can_perform_financial_txn(user) -> None:
    """Raise if user cannot perform both pay-in and pay-out (legacy entry point)."""
    assert_can_pay_in(user)
    assert_can_pay_out(user)


def user_access_flags_snapshot(user) -> dict[str, Any]:
    """Serializable access flags for API responses."""
    return {
        'is_active': bool(getattr(user, 'is_active', True)),
        'is_restricted': bool(getattr(user, 'is_restricted', False)),
        'payments_locked': bool(getattr(user, 'payments_locked', False)),
        'pay_in_allowed_when_disabled': bool(getattr(user, 'pay_in_allowed_when_disabled', False)),
        'may_login': user_may_login(user),
        'may_pay_in': user_may_pay_in(user),
        'may_pay_out': user_may_pay_out(user),
    }
