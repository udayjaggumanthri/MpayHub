"""
Build permission-aware KYC verification payloads for profile APIs.
"""
from __future__ import annotations

from django.utils import timezone

from apps.integrations.kyc.profile_sync import parse_kyc_dob


def _iso_dt(value) -> str:
    if value is None:
        return ''
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _dob_str(value) -> str:
    if value is None or value == '':
        return ''
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    parsed = parse_kyc_dob(value)
    return parsed.isoformat() if parsed else str(value)


_ADDRESS_KEY_ALIASES = (
    ('house', ('house',)),
    ('street', ('street',)),
    ('landmark', ('landmark',)),
    ('locality', ('locality', 'loc')),
    ('po', ('po', 'post_office')),
    ('subdist', ('subdist',)),
    ('vtc', ('vtc', 'city')),
    ('dist', ('dist', 'district')),
    ('state', ('state',)),
    ('pincode', ('pincode', 'pc', 'pin_code', 'pin')),
    ('country', ('country',)),
)


def _str_field(raw: dict, *keys: str) -> str:
    if not isinstance(raw, dict):
        return ''
    for key in keys:
        value = raw.get(key)
        if value is None or isinstance(value, (dict, list)):
            continue
        if isinstance(value, bool):
            return 'true' if value else 'false'
        text = str(value).strip()
        if text:
            return text
    return ''


def _address_parts(addr: dict | None) -> dict:
    if not isinstance(addr, dict):
        return {}
    parts = {}
    for canonical, aliases in _ADDRESS_KEY_ALIASES:
        value = _str_field(addr, *aliases)
        if value:
            parts[canonical] = value
    return parts


def _format_split_address(addr: dict) -> str:
    parts = _address_parts(addr) if isinstance(addr, dict) else {}
    order = ('house', 'street', 'landmark', 'locality', 'po', 'subdist', 'vtc', 'dist', 'state', 'pincode', 'country')
    return ', '.join(parts[key] for key in order if parts.get(key))


def _aadhaar_seeding_status(raw: dict) -> str:
    status = _str_field(raw, 'aadhaar_seeding_status')
    if status:
        return status
    linked = raw.get('aadhaar_linked')
    if linked is True:
        return 'Y'
    if linked is False:
        return 'R'
    return ''


def extract_pan_fields_from_raw(raw: dict | None) -> dict:
    if not isinstance(raw, dict):
        return {}
    extras = {
        'name_match_score': _str_field(raw, 'name_match_score'),
        'name_match_result': _str_field(raw, 'name_match_result'),
        'aadhaar_seeding_status': _aadhaar_seeding_status(raw),
        'aadhaar_seeding_status_desc': _str_field(raw, 'aadhaar_seeding_status_desc'),
        'father_name': _str_field(raw, 'father_name', 'fathername'),
        'message': _str_field(raw, 'message'),
        'pan_status': _str_field(raw, 'pan_status', 'status') or ('VALID' if raw.get('valid') else ''),
        'last_updated_at': _str_field(raw, 'last_updated_at'),
        'name_provided': _str_field(raw, 'name_provided'),
        'masked_aadhaar_number': _str_field(raw, 'masked_aadhaar_number'),
    }
    return {k: v for k, v in extras.items() if v}


def extract_aadhaar_fields_from_raw(raw: dict | None) -> dict:
    if not isinstance(raw, dict):
        return {}
    split = raw.get('split_address') if isinstance(raw.get('split_address'), dict) else {}
    nested_address = raw.get('address') if isinstance(raw.get('address'), dict) else {}
    present = raw.get('present_address')
    if isinstance(present, dict) and not nested_address:
        nested_address = present
        present_line = ''
    else:
        present_line = _str_field(raw, 'present_address')

    parts = {**_address_parts(nested_address), **_address_parts(split)}
    line = _format_split_address(parts) or present_line
    if not line:
        line = _str_field(raw, 'address')

    extras = {
        'care_of': _str_field(raw, 'care_of', 'careof'),
        'year_of_birth': _str_field(raw, 'year_of_birth'),
        'message': _str_field(raw, 'message'),
        'address': line,
        'district': parts.get('dist', ''),
        'state': parts.get('state', ''),
        'pincode': parts.get('pincode', ''),
        'country': parts.get('country', '') or _str_field(raw, 'country'),
    }
    return {k: v for k, v in extras.items() if v}


def _merge_identity_block(existing: dict, new: dict, *, fill_gaps_only: bool = False) -> dict:
    merged = dict(existing or {})
    for key, value in (new or {}).items():
        if value in (None, '', {}, []):
            continue
        if fill_gaps_only:
            if not merged.get(key):
                merged[key] = value
        else:
            merged[key] = value
    return merged


def _user_profile_hints(user) -> tuple[str, str]:
    from apps.users.models import UserProfile

    name = ''
    dob = ''
    profile = UserProfile.objects.filter(user=user).first()
    if profile:
        name = ' '.join(part for part in (profile.first_name, profile.last_name) if part).strip()
        if profile.date_of_birth:
            dob = profile.date_of_birth.isoformat()
    if not name:
        name = ' '.join(part for part in (getattr(user, 'first_name', ''), getattr(user, 'last_name', '')) if part).strip()
    return name, dob


def _default_pan_block(kyc) -> dict:
    return {
        'pan': kyc.pan or '',
        'name': '',
        'date_of_birth': '',
        'pan_type': '',
        'reference_id': '',
        'provider_code': '',
        'verified_at': _iso_dt(kyc.pan_verified_at),
        'name_match_score': '',
        'name_match_result': '',
        'aadhaar_seeding_status': '',
        'aadhaar_seeding_status_desc': '',
        'father_name': '',
        'message': '',
        'pan_status': '',
        'last_updated_at': '',
        'name_provided': '',
        'masked_aadhaar_number': '',
    }


def _default_aadhaar_block(kyc) -> dict:
    return {
        'uid_masked': kyc.aadhaar or '',
        'name': '',
        'date_of_birth': '',
        'gender': '',
        'reference_id': '',
        'provider_code': '',
        'verified_at': _iso_dt(kyc.aadhaar_verified_at),
        'care_of': '',
        'year_of_birth': '',
        'message': '',
        'address': '',
        'district': '',
        'state': '',
        'pincode': '',
        'country': '',
    }


def _finalize_pan_block(block: dict, kyc, user) -> dict:
    merged = _merge_identity_block(_default_pan_block(kyc), block, fill_gaps_only=True)
    profile_name, profile_dob = _user_profile_hints(user)
    merged['name_source'] = 'verified' if block.get('name') else ''
    merged['date_of_birth_source'] = 'verified' if block.get('date_of_birth') else ''
    if not merged.get('name') and profile_name:
        merged['name'] = profile_name
        merged['name_source'] = 'profile'
    if not merged.get('date_of_birth') and profile_dob:
        merged['date_of_birth'] = profile_dob
        merged['date_of_birth_source'] = 'profile'
    return merged


def _finalize_aadhaar_block(block: dict, kyc, user) -> dict:
    merged = _merge_identity_block(_default_aadhaar_block(kyc), block, fill_gaps_only=True)
    profile_name, profile_dob = _user_profile_hints(user)
    merged['name_source'] = 'verified' if block.get('name') else ''
    merged['date_of_birth_source'] = 'verified' if block.get('date_of_birth') else ''
    if not merged.get('name') and profile_name:
        merged['name'] = profile_name
        merged['name_source'] = 'profile'
    if not merged.get('date_of_birth') and profile_dob:
        merged['date_of_birth'] = profile_dob
        merged['date_of_birth_source'] = 'profile'
    return merged


def persist_pan_verified_identity(
    kyc,
    *,
    pan: str,
    name: str,
    dob,
    pan_type: str,
    provider_code: str,
    reference_id: str = '',
    verified_at=None,
    profile_updated: bool = False,
    raw: dict | None = None,
    fill_gaps_only: bool = False,
) -> None:
    identity = dict(kyc.verified_identity or {})
    block = {
        'pan': pan or '',
        'name': name or '',
        'date_of_birth': _dob_str(dob),
        'pan_type': pan_type or '',
        'reference_id': str(reference_id or ''),
        'provider_code': provider_code or '',
        'verified_at': _iso_dt(verified_at or timezone.now()),
    }
    block.update(extract_pan_fields_from_raw(raw))
    existing = identity.get('pan') if isinstance(identity.get('pan'), dict) else {}
    identity['pan'] = _merge_identity_block(existing, block, fill_gaps_only=fill_gaps_only)
    sources = list(identity.get('profile_sync_sources') or [])
    if profile_updated and 'pan' not in sources:
        sources.append('pan')
    identity['profile_sync_sources'] = sources
    if profile_updated:
        identity['profile_last_synced_at'] = _iso_dt(timezone.now())
    kyc.verified_identity = identity
    kyc.save(update_fields=['verified_identity', 'updated_at'])


def persist_aadhaar_verified_identity(
    kyc,
    *,
    uid_masked: str,
    name: str,
    dob,
    gender: str,
    provider_code: str,
    reference_id: str = '',
    verified_at=None,
    profile_updated: bool = False,
    raw: dict | None = None,
    fill_gaps_only: bool = False,
) -> None:
    identity = dict(kyc.verified_identity or {})
    block = {
        'uid_masked': uid_masked or '',
        'name': name or '',
        'date_of_birth': _dob_str(dob),
        'gender': gender or '',
        'reference_id': str(reference_id or ''),
        'provider_code': provider_code or '',
        'verified_at': _iso_dt(verified_at or timezone.now()),
    }
    block.update(extract_aadhaar_fields_from_raw(raw))
    existing = identity.get('aadhaar') if isinstance(identity.get('aadhaar'), dict) else {}
    identity['aadhaar'] = _merge_identity_block(existing, block, fill_gaps_only=fill_gaps_only)
    sources = list(identity.get('profile_sync_sources') or [])
    if profile_updated and 'aadhaar' not in sources:
        sources.append('aadhaar')
    identity['profile_sync_sources'] = sources
    if profile_updated:
        identity['profile_last_synced_at'] = _iso_dt(timezone.now())
    kyc.verified_identity = identity
    kyc.save(update_fields=['verified_identity', 'updated_at'])


def build_kyc_status_only(kyc) -> dict | None:
    if kyc is None:
        return None
    return {
        'pan_verified': bool(kyc.pan_verified),
        'aadhaar_verified': bool(kyc.aadhaar_verified),
        'verification_status': kyc.verification_status or 'pending',
    }


def build_kyc_verification_payload(kyc) -> dict | None:
    if kyc is None:
        return None
    user = getattr(kyc, 'user', None)
    identity = kyc.verified_identity if isinstance(kyc.verified_identity, dict) else {}
    pan_block = identity.get('pan') if isinstance(identity.get('pan'), dict) else {}
    aadhaar_block = identity.get('aadhaar') if isinstance(identity.get('aadhaar'), dict) else {}

    if kyc.pan_verified:
        pan_block = _finalize_pan_block(pan_block, kyc, user)
    else:
        pan_block = None

    if kyc.aadhaar_verified:
        aadhaar_block = _finalize_aadhaar_block(aadhaar_block, kyc, user)
    else:
        aadhaar_block = None

    sources = identity.get('profile_sync_sources') or []
    return {
        'pan_verified': bool(kyc.pan_verified),
        'aadhaar_verified': bool(kyc.aadhaar_verified),
        'verification_status': kyc.verification_status or 'pending',
        'pan': pan_block,
        'aadhaar': aadhaar_block,
        'profile_synced_from_kyc': bool(sources),
        'profile_last_synced_at': identity.get('profile_last_synced_at') or '',
    }


def viewer_may_see_full_kyc_verification(viewer, target_user) -> bool:
    if viewer is None or not getattr(viewer, 'is_authenticated', False):
        return False
    if getattr(viewer, 'role', None) == 'Admin' or getattr(viewer, 'is_superuser', False):
        return True
    return viewer.pk == target_user.pk
