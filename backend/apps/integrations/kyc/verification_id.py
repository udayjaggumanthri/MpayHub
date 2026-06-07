"""
Cashfree VRS verification_id helpers.

Cashfree allows only alphanumeric characters, dots, hyphens, and underscores.
"""
from __future__ import annotations

import re
import uuid

_CASHFREE_VID_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')


def sanitize_cashfree_verification_id(value: str, *, max_len: int = 50) -> str:
    """Strip disallowed characters and truncate."""
    cleaned = re.sub(r'[^A-Za-z0-9._-]', '', str(value or ''))
    return cleaned[:max_len]


def new_cashfree_verification_id(prefix: str, user, *, max_len: int = 50) -> str:
    """Generate a Cashfree-compliant verification_id for a user-scoped request."""
    safe_prefix = re.sub(r'[^A-Za-z0-9]', '', str(prefix or 'VID'))[:8] or 'VID'
    uid = re.sub(r'[^A-Za-z0-9]', '', str(getattr(user, 'user_id', None) or user.pk))
    suffix = uuid.uuid4().hex[:12]
    return sanitize_cashfree_verification_id(f'{safe_prefix}_{uid}_{suffix}', max_len=max_len)


def assert_cashfree_verification_id(value: str) -> str:
    vid = sanitize_cashfree_verification_id(value)
    if not vid or not _CASHFREE_VID_PATTERN.match(vid):
        raise ValueError(
            'verification_id can include only alphanum, dot, hyphen and underscores.'
        )
    return vid
