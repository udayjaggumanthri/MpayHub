"""
Cashfree DigiLocker webhook handling.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time

from django.db import transaction
from django.utils import timezone

from apps.integrations.kyc.registry import resolve_aadhaar_provider
from apps.users.models import KYC, KycDigilockerSession
from apps.integrations.kyc.profile_sync import extract_dob_from_raw
from apps.integrations.kyc.profile_sync_orchestrator import handle_post_kyc_profile_sync
from apps.users.services import parse_kyc_dob_safe, sync_kyc_verification_status

logger = logging.getLogger(__name__)

WEBHOOK_MAX_SKEW_SECONDS = 300


def verify_cashfree_webhook_signature(
    raw_body: bytes,
    signature_header: str,
    timestamp_header: str,
    secret: str,
) -> bool:
    secret = str(secret or '').strip()
    if not secret:
        return False
    sig = str(signature_header or '').strip()
    ts = str(timestamp_header or '').strip()
    if not sig or not ts:
        return False
    try:
        ts_int = int(ts)
        if abs(int(time.time()) - ts_int) > WEBHOOK_MAX_SKEW_SECONDS:
            return False
    except (TypeError, ValueError):
        return False
    try:
        message = f'{ts}{raw_body.decode("utf-8")}'.encode('utf-8')
        digest = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode('utf-8')
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False


def _apply_aadhaar_verified(user, *, masked_uid: str, doc=None, provider_code: str = '') -> bool:
    from apps.users.kyc_display import persist_aadhaar_verified_identity

    with transaction.atomic():
        kyc, _ = KYC.objects.select_for_update().get_or_create(user=user)
        if not kyc.pan_verified:
            logger.warning('DigiLocker webhook ignored: PAN not verified for user %s', user.pk)
            return False
        if kyc.aadhaar_verified:
            return True
        if masked_uid and KYC.objects.filter(aadhaar=masked_uid).exclude(user=user).exists():
            logger.warning('DigiLocker UID already linked to another user; aborting verification')
            return False

        if masked_uid:
            kyc.aadhaar = masked_uid
        kyc.aadhaar_verified = True
        kyc.aadhaar_verified_at = timezone.now()
        kyc.save(update_fields=['aadhaar', 'aadhaar_verified', 'aadhaar_verified_at', 'updated_at'])

        profile_updated = False
        if doc is not None:
            dob = extract_dob_from_raw(doc.raw) or parse_kyc_dob_safe(getattr(doc, 'date_of_birth', ''))
            sync_result = handle_post_kyc_profile_sync(
                user,
                source='aadhaar',
                trigger='webhook',
                verified_name=getattr(doc, 'name', '') or '',
                verified_dob=dob,
                metadata={'provider_code': provider_code},
            )
            profile_updated = sync_result.profile_updated
            persist_aadhaar_verified_identity(
                kyc,
                uid_masked=masked_uid or kyc.aadhaar or '',
                name=getattr(doc, 'name', '') or '',
                dob=dob,
                gender=getattr(doc, 'gender', '') or '',
                provider_code=provider_code or getattr(doc, 'provider_code', '') or 'cashfree_digilocker',
                reference_id=str(doc.raw.get('reference_id') or '') if isinstance(getattr(doc, 'raw', None), dict) else '',
                verified_at=kyc.aadhaar_verified_at,
                profile_updated=profile_updated,
                raw=doc.raw if isinstance(getattr(doc, 'raw', None), dict) else None,
            )
        sync_kyc_verification_status(kyc)
    return True


def handle_digilocker_webhook(payload: dict) -> dict:
    event_type = str(payload.get('event_type') or '')
    data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
    verification_id = str(data.get('verification_id') or '')
    status = str(data.get('status') or '')
    reference_id = str(data.get('reference_id') or '')

    session = None
    if verification_id:
        session = KycDigilockerSession.objects.filter(
            verification_id=verification_id,
            is_deleted=False,
        ).select_related('user').first()

    if session:
        existing_raw = session.raw_status if isinstance(session.raw_status, dict) else {}
        merged_raw = dict(data)
        if 'document' in existing_raw and 'document' not in merged_raw:
            merged_raw['document'] = existing_raw['document']
        session.status = status or session.status
        session.reference_id = reference_id or session.reference_id or ''
        session.raw_status = merged_raw
        if event_type == 'DIGILOCKER_VERIFICATION_SUCCESS' and status == 'AUTHENTICATED':
            session.completed_at = timezone.now()
        session.save(
            update_fields=['status', 'reference_id', 'raw_status', 'completed_at', 'updated_at']
        )

    if event_type == 'DIGILOCKER_VERIFICATION_SUCCESS' and session and status == 'AUTHENTICATED':
        existing_kyc = KYC.objects.filter(user=session.user).first()
        if existing_kyc and existing_kyc.aadhaar_verified:
            return {
                'handled': True,
                'event_type': event_type,
                'verification_id': verification_id,
                'skipped': 'already_verified',
            }
        try:
            provider = resolve_aadhaar_provider()
            doc = provider.fetch_document(verification_id=verification_id, document_type='AADHAAR')
            if isinstance(doc.raw, dict):
                raw_status = dict(session.raw_status or {})
                raw_status['document'] = doc.raw
                session.raw_status = raw_status
                session.save(update_fields=['raw_status', 'updated_at'])
            applied = _apply_aadhaar_verified(
                session.user,
                masked_uid=doc.uid_masked,
                doc=doc,
                provider_code=provider.provider_code,
            )
            if not applied:
                return {'handled': False, 'event_type': event_type, 'error': 'aadhaar_verification_rejected'}
        except Exception as e:
            logger.exception('DigiLocker webhook document fetch failed: %s', e)
            return {'handled': False, 'event_type': event_type, 'error': str(e)}

    return {'handled': True, 'event_type': event_type, 'verification_id': verification_id}
