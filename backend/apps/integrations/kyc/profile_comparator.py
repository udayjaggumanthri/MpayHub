"""
Compare user profile name/DOB against verified KYC provider values.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from apps.integrations.kyc.profile_sync import parse_kyc_dob


def normalize_kyc_name(value: str) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip().upper())


def _profile_full_name(user) -> str:
    from apps.users.models import UserProfile

    profile = UserProfile.objects.filter(user=user).first()
    if profile:
        name = ' '.join(part for part in (profile.first_name, profile.last_name) if part).strip()
        if name:
            return name
    return ' '.join(part for part in (getattr(user, 'first_name', ''), getattr(user, 'last_name', '')) if part).strip()


def _profile_date_of_birth(user) -> date | None:
    from apps.users.models import UserProfile

    profile = UserProfile.objects.filter(user=user).first()
    if profile and profile.date_of_birth:
        return profile.date_of_birth
    return None


@dataclass
class ProfileKycDiff:
    has_confirmation_mismatch: bool
    name_differs: bool
    dob_differs: bool
    profile_full_name: str
    profile_date_of_birth: date | None
    verified_full_name: str
    verified_date_of_birth: date | None
    source: str

    @property
    def has_verified_values(self) -> bool:
        return bool(self.verified_full_name or self.verified_date_of_birth)


def compare_profile_with_kyc(
    user,
    *,
    verified_name: str = '',
    verified_dob: date | None = None,
    source: str = 'pan',
) -> ProfileKycDiff:
    profile_name = _profile_full_name(user)
    profile_dob = _profile_date_of_birth(user)
    v_name = str(verified_name or '').strip()
    v_dob = verified_dob if isinstance(verified_dob, date) else parse_kyc_dob(verified_dob)

    name_differs = bool(
        profile_name
        and v_name
        and normalize_kyc_name(profile_name) != normalize_kyc_name(v_name)
    )
    dob_differs = bool(profile_dob and v_dob and profile_dob != v_dob)

    # Empty profile fields are auto-filled without confirmation (handled by orchestrator).
    has_confirmation_mismatch = name_differs or dob_differs

    return ProfileKycDiff(
        has_confirmation_mismatch=has_confirmation_mismatch,
        name_differs=name_differs,
        dob_differs=dob_differs,
        profile_full_name=profile_name,
        profile_date_of_birth=profile_dob,
        verified_full_name=v_name,
        verified_date_of_birth=v_dob,
        source=source,
    )


def diff_to_mismatch_payload(diff: ProfileKycDiff) -> dict:
    return {
        'name': {
            'current': diff.profile_full_name or '',
            'verified': diff.verified_full_name or '',
            'differs': diff.name_differs,
        },
        'date_of_birth': {
            'current': diff.profile_date_of_birth.isoformat() if diff.profile_date_of_birth else '',
            'verified': diff.verified_date_of_birth.isoformat() if diff.verified_date_of_birth else '',
            'differs': diff.dob_differs,
        },
        'source': diff.source,
    }
