"""
Audit store and API payloads for KYC → profile synchronization.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.integrations.kyc.profile_comparator import ProfileKycDiff, diff_to_mismatch_payload
from apps.integrations.kyc.profile_sync import split_kyc_full_name


def _token_ttl_minutes() -> int:
    return int(getattr(settings, 'KYC_PROFILE_SYNC_TOKEN_TTL_MINUTES', 30))


def _new_sync_token() -> str:
    return uuid.uuid4().hex


def create_pending_audit(
    user,
    diff: ProfileKycDiff,
    *,
    source: str,
    trigger: str,
    metadata: dict | None = None,
):
    from apps.users.models import KycProfileSyncAudit

    before_first, before_last = split_kyc_full_name(diff.profile_full_name)
    token = _new_sync_token()
    expires_at = timezone.now() + timedelta(minutes=_token_ttl_minutes())
    audit = KycProfileSyncAudit.objects.create(
        user=user,
        source=source,
        trigger=trigger,
        status='pending',
        before_first_name=before_first[:150],
        before_last_name=before_last[:150],
        before_date_of_birth=diff.profile_date_of_birth,
        verified_full_name=diff.verified_full_name[:300],
        verified_date_of_birth=diff.verified_date_of_birth,
        sync_token=token,
        sync_token_expires_at=expires_at,
        metadata=metadata if isinstance(metadata, dict) else {},
    )
    return audit, token, expires_at


def record_auto_applied_audit(
    user,
    diff: ProfileKycDiff,
    *,
    source: str,
    trigger: str,
    after_first_name: str,
    after_last_name: str,
    after_date_of_birth,
    metadata: dict | None = None,
):
    from apps.users.models import KycProfileSyncAudit

    before_first, before_last = split_kyc_full_name(diff.profile_full_name)
    return KycProfileSyncAudit.objects.create(
        user=user,
        source=source,
        trigger=trigger,
        status='auto_applied',
        before_first_name=before_first[:150],
        before_last_name=before_last[:150],
        before_date_of_birth=diff.profile_date_of_birth,
        verified_full_name=diff.verified_full_name[:300],
        verified_date_of_birth=diff.verified_date_of_birth,
        after_first_name=after_first_name[:150],
        after_last_name=after_last_name[:150],
        after_date_of_birth=after_date_of_birth,
        confirmed_at=timezone.now(),
        metadata=metadata if isinstance(metadata, dict) else {},
    )


def get_pending_audits_for_user(user):
    from apps.users.models import KycProfileSyncAudit

    now = timezone.now()
    return (
        KycProfileSyncAudit.objects.filter(
            user=user,
            status='pending',
            is_deleted=False,
            sync_token_expires_at__gt=now,
        )
        .order_by('-created_at')
    )


def serialize_pending_audit(audit) -> dict:
    from apps.integrations.kyc.profile_comparator import normalize_kyc_name

    profile_name = ' '.join(p for p in (audit.before_first_name, audit.before_last_name) if p).strip()
    verified_name = audit.verified_full_name or ''
    name_differs = bool(
        profile_name
        and verified_name
        and normalize_kyc_name(profile_name) != normalize_kyc_name(verified_name)
    )
    dob_differs = bool(
        audit.before_date_of_birth
        and audit.verified_date_of_birth
        and audit.before_date_of_birth != audit.verified_date_of_birth
    )
    diff = ProfileKycDiff(
        has_confirmation_mismatch=True,
        name_differs=name_differs,
        dob_differs=dob_differs,
        profile_full_name=profile_name,
        profile_date_of_birth=audit.before_date_of_birth,
        verified_full_name=verified_name,
        verified_date_of_birth=audit.verified_date_of_birth,
        source=audit.source or '',
    )
    return {
        'audit_id': audit.id,
        'sync_token': audit.sync_token,
        'expires_at': audit.sync_token_expires_at.isoformat() if audit.sync_token_expires_at else '',
        'source': audit.source,
        'trigger': audit.trigger,
        'mismatch': diff_to_mismatch_payload(diff),
        'message': 'Your profile details differ from verified KYC records.',
    }


def serialize_audit_row(audit) -> dict:
    return {
        'id': audit.id,
        'source': audit.source,
        'trigger': audit.trigger,
        'status': audit.status,
        'before': {
            'first_name': audit.before_first_name,
            'last_name': audit.before_last_name,
            'date_of_birth': audit.before_date_of_birth.isoformat() if audit.before_date_of_birth else '',
        },
        'verified': {
            'full_name': audit.verified_full_name,
            'date_of_birth': audit.verified_date_of_birth.isoformat() if audit.verified_date_of_birth else '',
        },
        'after': {
            'first_name': audit.after_first_name,
            'last_name': audit.after_last_name,
            'date_of_birth': audit.after_date_of_birth.isoformat() if audit.after_date_of_birth else '',
        },
        'confirmed_at': audit.confirmed_at.isoformat() if audit.confirmed_at else '',
        'declined_at': audit.declined_at.isoformat() if audit.declined_at else '',
        'created_at': audit.created_at.isoformat() if audit.created_at else '',
    }
