"""
Sync authoritative KYC provider fields into User + UserProfile.
"""
from __future__ import annotations

from datetime import date, datetime


def parse_kyc_dob(value) -> date | None:
    if value is None or value == '':
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def split_kyc_full_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in str(full_name or '').strip().split() if p]
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return ' '.join(parts[:-1]), parts[-1]


def extract_dob_from_raw(raw: dict) -> date | None:
    if not isinstance(raw, dict):
        return None
    for key in ('dob', 'date_of_birth', 'dateOfBirth', 'birth_date'):
        if raw.get(key):
            parsed = parse_kyc_dob(raw.get(key))
            if parsed:
                return parsed
    return None


def build_kyc_details(
    *,
    pan: str = '',
    name: str = '',
    dob: date | None = None,
    aadhaar_masked: str = '',
    pan_type: str = '',
    profile_updated: bool = False,
) -> dict:
    return {
        'pan': pan or '',
        'name': name or '',
        'date_of_birth': dob.isoformat() if isinstance(dob, date) else '',
        'aadhaar_masked': aadhaar_masked or '',
        'pan_type': pan_type or '',
        'profile_updated': bool(profile_updated),
    }


def apply_profile_sync(user, *, full_name: str | None = None, dob=None) -> bool:
    """
    Apply verified KYC name/DOB to User + UserProfile.
    Returns True if any profile field was updated.
    """
    from apps.users.models import UserProfile

    changed = False
    parsed_dob = dob if isinstance(dob, date) else parse_kyc_dob(dob)

    if full_name:
        first, last = split_kyc_full_name(full_name)
        if first:
            if user.first_name != first or user.last_name != last:
                user.first_name = first[:150]
                user.last_name = last[:150]
                user.save(update_fields=['first_name', 'last_name', 'updated_at'])
                changed = True

            profile = UserProfile.objects.filter(user=user).first()
            if profile:
                profile_updates = []
                if profile.first_name != first or profile.last_name != last:
                    profile.first_name = first[:100]
                    profile.last_name = last[:100]
                    profile_updates.extend(['first_name', 'last_name'])
                if parsed_dob and profile.date_of_birth != parsed_dob:
                    profile.date_of_birth = parsed_dob
                    profile_updates.append('date_of_birth')
                if profile_updates:
                    profile.save(update_fields=profile_updates + ['updated_at'])
                    changed = True
            elif parsed_dob:
                UserProfile.objects.create(
                    user=user,
                    first_name=first[:100],
                    last_name=last[:100],
                    date_of_birth=parsed_dob,
                )
                changed = True
    elif parsed_dob:
        profile = UserProfile.objects.filter(user=user).first()
        if profile and profile.date_of_birth != parsed_dob:
            profile.date_of_birth = parsed_dob
            profile.save(update_fields=['date_of_birth', 'updated_at'])
            changed = True

    return changed


def sync_profile_from_kyc_response(user, *, full_name: str | None = None, dob=None) -> bool:
    """Backward-compatible alias for apply_profile_sync."""
    return apply_profile_sync(user, full_name=full_name, dob=dob)
