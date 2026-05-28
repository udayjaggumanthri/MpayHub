"""
Central registry for user access-control error codes and copy.

Kept separate from enforcement (financial_access) so messages stay consistent
across API errors, serializers, and admin responses without tight coupling.
"""
from __future__ import annotations

from typing import Any

# Stable codes returned in PermissionDenied detail and API error payloads.
ACCESS_CODE_ROLE_FINANCIAL_BLOCKED = 'ROLE_FINANCIAL_BLOCKED'
ACCESS_CODE_USER_DISABLED = 'USER_DISABLED'
ACCESS_CODE_USER_RESTRICTED = 'USER_RESTRICTED'
ACCESS_CODE_USER_PAYMENTS_LOCKED = 'USER_PAYMENTS_LOCKED'

ALL_ACCESS_CODES = frozenset(
    {
        ACCESS_CODE_ROLE_FINANCIAL_BLOCKED,
        ACCESS_CODE_USER_DISABLED,
        ACCESS_CODE_USER_RESTRICTED,
        ACCESS_CODE_USER_PAYMENTS_LOCKED,
    }
)

_CATALOG: dict[str, dict[str, str]] = {
    ACCESS_CODE_ROLE_FINANCIAL_BLOCKED: {
        'message': (
            'Your role cannot perform wallet transactions. '
            'Use the team and commission reports instead.'
        ),
        'title': 'Transactions not available',
    },
    ACCESS_CODE_USER_DISABLED: {
        'message': 'Your account is disabled. Contact your administrator.',
        'title': 'Account disabled',
    },
    ACCESS_CODE_USER_RESTRICTED: {
        'message': (
            'Your account is restricted to read-only access. '
            'This action is not available.'
        ),
        'title': 'Read-only account',
    },
    ACCESS_CODE_USER_PAYMENTS_LOCKED: {
        'message': (
            'Payments are locked on your account. '
            'You may still use pay-in and reports where allowed.'
        ),
        'title': 'Payments locked',
    },
}


def user_message_for_code(code: str, *, fallback: str | None = None) -> str:
    entry = _CATALOG.get(code or '')
    if entry:
        return entry['message']
    return fallback or 'You do not have permission to perform this action.'


def title_for_code(code: str) -> str:
    return _CATALOG.get(code or '', {}).get('title', 'Access limited')


def access_error_detail(code: str, message: str | None = None) -> dict[str, str]:
    """DRF PermissionDenied detail shape consumed by the global exception handler."""
    return {
        'code': code,
        'message': message or user_message_for_code(code),
    }


def is_access_error_detail(detail: Any) -> bool:
    return isinstance(detail, dict) and str(detail.get('code') or '') in ALL_ACCESS_CODES
