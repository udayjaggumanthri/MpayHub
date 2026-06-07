"""
Orchestrate KYC → profile sync with mismatch confirmation and audit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.conf import settings

from apps.integrations.kyc.profile_comparator import (
    ProfileKycDiff,
    compare_profile_with_kyc,
    diff_to_mismatch_payload,
)
from apps.integrations.kyc.profile_sync import apply_profile_sync, split_kyc_full_name
from apps.users.kyc_profile_sync_audit import create_pending_audit, record_auto_applied_audit


@dataclass
class ProfileSyncResult:
    status: str  # no_change | auto_applied | pending_confirmation
    profile_updated: bool
    sync_token: str = ''
    sync_expires_at: str = ''
    audit_id: int | None = None
    mismatch: dict | None = None
    message: str = ''

    def to_api_dict(self) -> dict | None:
        if self.status == 'no_change':
            return None
        payload = {
            'status': self.status,
            'profile_updated': self.profile_updated,
            'message': self.message,
        }
        if self.status == 'pending_confirmation':
            payload.update({
                'sync_token': self.sync_token,
                'expires_at': self.sync_expires_at,
                'audit_id': self.audit_id,
                'mismatch': self.mismatch or {},
            })
        return payload


def _require_confirm_on_mismatch() -> bool:
    return bool(getattr(settings, 'KYC_PROFILE_SYNC_REQUIRE_CONFIRM_ON_MISMATCH', True))


def _auto_fill_empty() -> bool:
    return bool(getattr(settings, 'KYC_PROFILE_SYNC_AUTO_FILL_EMPTY', True))


def _should_auto_apply(diff: ProfileKycDiff) -> bool:
    if not diff.has_verified_values:
        return False
    if diff.has_confirmation_mismatch:
        return not _require_confirm_on_mismatch()
    return True


def _mark_kyc_profile_synced(user, source: str) -> None:
    from apps.users.models import KYC

    kyc = KYC.objects.filter(user=user).first()
    if not kyc:
        return
    identity = dict(kyc.verified_identity or {})
    sources = list(identity.get('profile_sync_sources') or [])
    if source not in sources:
        sources.append(source)
    identity['profile_sync_sources'] = sources
    from django.utils import timezone

    identity['profile_last_synced_at'] = timezone.now().isoformat()
    kyc.verified_identity = identity
    kyc.save(update_fields=['verified_identity', 'updated_at'])


def handle_post_kyc_profile_sync(
    user,
    *,
    source: str,
    trigger: str,
    verified_name: str = '',
    verified_dob: date | None = None,
    metadata: dict | None = None,
) -> ProfileSyncResult:
    diff = compare_profile_with_kyc(
        user,
        verified_name=verified_name,
        verified_dob=verified_dob,
        source=source,
    )

    if not diff.has_verified_values:
        return ProfileSyncResult(status='no_change', profile_updated=False)

    if diff.has_confirmation_mismatch and _require_confirm_on_mismatch():
        audit, token, expires_at = create_pending_audit(
            user,
            diff,
            source=source,
            trigger=trigger,
            metadata=metadata,
        )
        return ProfileSyncResult(
            status='pending_confirmation',
            profile_updated=False,
            sync_token=token,
            sync_expires_at=expires_at.isoformat(),
            audit_id=audit.id,
            mismatch=diff_to_mismatch_payload(diff),
            message='Your profile details differ from verified KYC records. Confirm to update your profile.',
        )

    if not _should_auto_apply(diff):
        return ProfileSyncResult(status='no_change', profile_updated=False)

    # Auto-apply: exact match refresh, or fill empty profile fields when enabled.
    if diff.has_confirmation_mismatch and not _auto_fill_empty():
        return ProfileSyncResult(status='no_change', profile_updated=False)

    changed = apply_profile_sync(
        user,
        full_name=diff.verified_full_name or None,
        dob=diff.verified_date_of_birth,
    )
    if not changed:
        return ProfileSyncResult(status='no_change', profile_updated=False)

    user.refresh_from_db()
    after_first = user.first_name or ''
    after_last = user.last_name or ''
    from apps.users.models import UserProfile

    profile = UserProfile.objects.filter(user=user).first()
    after_dob = profile.date_of_birth if profile else None

    record_auto_applied_audit(
        user,
        diff,
        source=source,
        trigger=trigger,
        after_first_name=after_first,
        after_last_name=after_last,
        after_date_of_birth=after_dob,
        metadata=metadata,
    )
    _mark_kyc_profile_synced(user, source)

    return ProfileSyncResult(
        status='auto_applied',
        profile_updated=True,
        message='Profile name and date of birth were updated from verified KYC records.',
    )


def confirm_profile_sync(user, *, sync_token: str) -> ProfileSyncResult:
    from django.db import transaction
    from django.utils import timezone

    from apps.users.models import KycProfileSyncAudit

    token = str(sync_token or '').strip()
    if not token:
        raise ValueError('sync_token is required.')

    with transaction.atomic():
        audit = (
            KycProfileSyncAudit.objects.select_for_update()
            .filter(user=user, sync_token=token, is_deleted=False)
            .first()
        )
        if not audit:
            raise ValueError('Invalid or expired sync request.')
        if audit.status == 'applied':
            return ProfileSyncResult(
                status='auto_applied',
                profile_updated=True,
                message='Profile was already updated from verified KYC records.',
            )
        if audit.status == 'declined':
            raise ValueError('This sync request was declined. Start a new verification to sync again.')
        if audit.status != 'pending':
            raise ValueError('This sync request is no longer valid.')
        if audit.sync_token_expires_at and audit.sync_token_expires_at < timezone.now():
            raise ValueError('This sync request has expired. Verify KYC again or contact support.')

        changed = apply_profile_sync(
            user,
            full_name=audit.verified_full_name or None,
            dob=audit.verified_date_of_birth,
        )
        user.refresh_from_db()
        after_first = user.first_name or ''
        after_last = user.last_name or ''
        from apps.users.models import UserProfile

        profile = UserProfile.objects.filter(user=user).first()
        after_dob = profile.date_of_birth if profile else None

        audit.status = 'applied'
        audit.after_first_name = after_first[:150]
        audit.after_last_name = after_last[:150]
        audit.after_date_of_birth = after_dob
        audit.confirmed_at = timezone.now()
        audit.actor_user = user
        audit.save(
            update_fields=[
                'status',
                'after_first_name',
                'after_last_name',
                'after_date_of_birth',
                'confirmed_at',
                'actor_user',
                'updated_at',
            ]
        )

    if changed:
        _mark_kyc_profile_synced(user, audit.source)

    return ProfileSyncResult(
        status='auto_applied',
        profile_updated=changed,
        message='Profile updated from verified KYC records.' if changed else 'Profile already matches verified records.',
    )


def decline_profile_sync(user, *, sync_token: str) -> ProfileSyncResult:
    from django.db import transaction
    from django.utils import timezone

    from apps.users.models import KycProfileSyncAudit

    token = str(sync_token or '').strip()
    if not token:
        raise ValueError('sync_token is required.')

    with transaction.atomic():
        audit = (
            KycProfileSyncAudit.objects.select_for_update()
            .filter(user=user, sync_token=token, is_deleted=False)
            .first()
        )
        if not audit:
            raise ValueError('Invalid or expired sync request.')
        if audit.status == 'declined':
            return ProfileSyncResult(
                status='no_change',
                profile_updated=False,
                message='Profile was not updated. Your verified KYC records remain on file.',
            )
        if audit.status in ('applied', 'auto_applied'):
            raise ValueError('Profile was already synced from verified KYC records.')
        if audit.status != 'pending':
            raise ValueError('This sync request is no longer valid.')

        audit.status = 'declined'
        audit.declined_at = timezone.now()
        audit.actor_user = user
        audit.save(update_fields=['status', 'declined_at', 'actor_user', 'updated_at'])

    return ProfileSyncResult(
        status='no_change',
        profile_updated=False,
        message='Profile was not updated. Your verified KYC records remain on file; you can sync later from Profile → Verification.',
    )
