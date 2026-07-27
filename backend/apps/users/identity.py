"""
Public user identity — immutable member serial + mutable role display code.

Layers:
  users.id            — internal PK / FKs (never changes)
  member_number       — global serial (never changes, never reused)
  member_id           — MPH{number} permanent public id (never changes)
  display_code        — role prefix + number (prefix updates on role change)
  user_id (legacy)    — preserved as-is for existing rows; new rows get member_id
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from apps.authentication.models import User

# Display prefixes for the new public display_code (role-facing).
ROLE_DISPLAY_PREFIX = {
    'Admin': 'A',
    'Super Distributor': 'SD',
    'Master Distributor': 'MD',
    'Distributor': 'D',
    'Retailer': 'R',
}

MEMBER_ID_PREFIX = 'MPH'
SEQUENCE_KEY = 'global'
MIN_PAD = 6


def role_display_prefix(role: str | None) -> str:
    role = (role or '').strip()
    if role not in ROLE_DISPLAY_PREFIX:
        raise ValueError(f'Unknown role for display code: {role!r}')
    return ROLE_DISPLAY_PREFIX[role]


def format_member_id(member_number: int) -> str:
    n = int(member_number)
    if n < 1:
        raise ValueError('member_number must be >= 1')
    width = max(MIN_PAD, len(str(n)))
    return f'{MEMBER_ID_PREFIX}{n:0{width}d}'


def format_display_code(role: str | None, member_number: int) -> str:
    prefix = role_display_prefix(role)
    n = int(member_number)
    if n < 1:
        raise ValueError('member_number must be >= 1')
    width = max(MIN_PAD, len(str(n)))
    return f'{prefix}{n:0{width}d}'


def public_display_code(user: 'User') -> str:
    """Preferred human-facing code for UI / notifications (with legacy fallback)."""
    code = (getattr(user, 'display_code', None) or '').strip()
    if code:
        return code
    legacy = (getattr(user, 'user_id', None) or '').strip()
    if legacy:
        return legacy
    mid = (getattr(user, 'member_id', None) or '').strip()
    if mid:
        return mid
    return str(user.pk)


def public_member_id(user: 'User') -> str:
    mid = (getattr(user, 'member_id', None) or '').strip()
    if mid:
        return mid
    return public_display_code(user)


@transaction.atomic
def allocate_member_number() -> int:
    """
    Allocate the next global member_number under a row lock.
    Numbers are never reused after soft or hard deletion.
    """
    from apps.authentication.models import MemberNumberSequence

    seq, _created = MemberNumberSequence.objects.select_for_update().get_or_create(
        key=SEQUENCE_KEY,
        defaults={'next_value': 1},
    )
    number = int(seq.next_value)
    if number < 1:
        number = 1
    seq.next_value = number + 1
    seq.save(update_fields=['next_value', 'updated_at'])
    return number


def assign_identity_fields(user: 'User', *, role: str | None = None) -> dict:
    """
    Allocate and attach identity fields onto an unsaved/saved User instance.
    Does not call save(). Returns the assigned values.
    """
    role = role if role is not None else getattr(user, 'role', None)
    number = allocate_member_number()
    member_id = format_member_id(number)
    display_code = format_display_code(role, number)
    user.member_number = number
    user.member_id = member_id
    user.display_code = display_code
    return {
        'member_number': number,
        'member_id': member_id,
        'display_code': display_code,
    }


def recompute_display_code(user: 'User', new_role: str) -> str:
    """Recompute display_code from existing member_number + new role. Does not save."""
    number = getattr(user, 'member_number', None)
    if number is None:
        raise ValueError('User has no member_number; run identity backfill first.')
    code = format_display_code(new_role, int(number))
    user.display_code = code
    return code


def identity_payload(user: 'User') -> dict:
    """Compact identity dict for hierarchy / nested API nodes."""
    return {
        'id': user.pk,
        'user_id': getattr(user, 'user_id', None) or '',
        'legacy_user_id': getattr(user, 'user_id', None) or '',
        'member_number': getattr(user, 'member_number', None),
        'member_id': getattr(user, 'member_id', None) or '',
        'display_code': getattr(user, 'display_code', None) or '',
        'role': getattr(user, 'role', None) or '',
    }
