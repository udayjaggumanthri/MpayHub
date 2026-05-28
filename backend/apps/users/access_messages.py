"""Human-readable admin API messages after access-control changes."""
from __future__ import annotations

from apps.authentication.models import User


def message_for_access_controls_update(user: User, patch: dict) -> str:
    """Build a specific success message from the fields that were changed."""
    if 'is_active' in patch:
        if patch['is_active']:
            return f'{_display(user)} can sign in and use the platform normally.'
        if patch.get('pay_in_allowed_when_disabled'):
            return (
                f'{_display(user)} is disabled for full access but may still sign in '
                f'to load money (pay-in only).'
            )
        return f'{_display(user)} is disabled and cannot sign in until re-enabled.'

    if patch.get('is_restricted') is True:
        return f'{_display(user)} is now restricted to read-only (reports and profile).'
    if patch.get('is_restricted') is False:
        return f'{_display(user)} restriction removed; pay-in and payments follow other flags.'

    if patch.get('payments_locked') is True:
        return (
            f'{_display(user)} payments are locked (no payout, BBPS, or transfers). '
            f'Pay-in remains available unless restricted or disabled.'
        )
    if patch.get('payments_locked') is False:
        return f'{_display(user)} payment lock removed.'

    return 'User access controls updated successfully.'


def _display(user: User) -> str:
    name = (user.get_full_name() or '').strip()
    return name or str(user.user_id or user.pk)
