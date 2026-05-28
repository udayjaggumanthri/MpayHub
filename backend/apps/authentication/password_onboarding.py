"""
Temporary password issuance for hierarchy onboarding (loosely coupled from views/serializers).
"""
import secrets
import string

from apps.authentication.models import User

_PASSWORD_ALPHABET = string.ascii_letters + string.digits + '!@#$%&*'
_MIN_LENGTH = 8


def _meets_password_policy(password: str) -> bool:
    if len(password) < _MIN_LENGTH:
        return False
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    return has_letter and has_digit


def generate_temporary_password(length: int = 12) -> str:
    """Cryptographically random password meeting minimum policy (8+ chars, letter + digit)."""
    length = max(length, _MIN_LENGTH)
    for _ in range(64):
        password = ''.join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))
        if _meets_password_policy(password):
            return password
    raise RuntimeError('Failed to generate a compliant temporary password.')


def issue_temporary_password(user: User) -> str:
    """
    Set a unique temporary password and require OTP reset on first login.
    Returns plaintext once for email/API handoff.
    """
    plain = generate_temporary_password()
    user.set_password(plain)
    user.must_change_password = True
    user.save(update_fields=['password', 'must_change_password', 'updated_at'])
    return plain


def clear_must_change_password(user: User) -> None:
    """Clear forced-reset flag after successful password change."""
    if not user.must_change_password:
        return
    user.must_change_password = False
    user.save(update_fields=['must_change_password', 'updated_at'])
