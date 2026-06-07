from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.integrations.kyc.profile_sync import extract_dob_from_raw, parse_kyc_dob
from apps.users.kyc_display import persist_aadhaar_verified_identity, persist_pan_verified_identity
from apps.users.models import KYC, KycDigilockerSession, KycVerificationAttempt


def _pan_block_incomplete(block: dict) -> bool:
    if not isinstance(block, dict) or not block:
        return True
    return not all(block.get(key) for key in ('name', 'date_of_birth'))


def _aadhaar_block_incomplete(block: dict) -> bool:
    if not isinstance(block, dict) or not block:
        return True
    return not all(block.get(key) for key in ('name', 'date_of_birth', 'gender'))


class Command(BaseCommand):
    help = 'Backfill KYC.verified_identity from audit tables for already-verified users.'

    def handle(self, *args, **options):
        updated = 0
        for kyc in KYC.objects.select_related('user').filter(is_deleted=False):
            identity = kyc.verified_identity if isinstance(kyc.verified_identity, dict) else {}
            changed = False

            if kyc.pan_verified and _pan_block_incomplete(identity.get('pan')):
                attempt = (
                    KycVerificationAttempt.objects.filter(user=kyc.user, is_deleted=False)
                    .order_by('-created_at')
                    .first()
                )
                meta = attempt.response_meta if attempt and isinstance(attempt.response_meta, dict) else {}
                dob = parse_kyc_dob(meta.get('date_of_birth'))
                persist_pan_verified_identity(
                    kyc,
                    pan=kyc.pan or '',
                    name=str(meta.get('registered_name') or ''),
                    dob=dob,
                    pan_type=str(meta.get('pan_type') or ''),
                    provider_code=(attempt.provider_code if attempt else '') or 'cashfree_pan',
                    reference_id=(attempt.reference_id if attempt else '') or '',
                    verified_at=kyc.pan_verified_at or (attempt.created_at if attempt else timezone.now()),
                    profile_updated=False,
                    raw={
                        'name_match_score': meta.get('name_match_score'),
                        'name_match_result': meta.get('name_match_result'),
                        'aadhaar_seeding_status': meta.get('aadhaar_seeding_status'),
                        'father_name': meta.get('father_name'),
                        'message': meta.get('message'),
                        'status': meta.get('pan_status'),
                    },
                    fill_gaps_only=True,
                )
                changed = True

            kyc.refresh_from_db(fields=['verified_identity'])
            identity = kyc.verified_identity if isinstance(kyc.verified_identity, dict) else {}

            if kyc.aadhaar_verified and _aadhaar_block_incomplete(identity.get('aadhaar')):
                session = (
                    KycDigilockerSession.objects.filter(
                        user=kyc.user,
                        is_deleted=False,
                        completed_at__isnull=False,
                    )
                    .order_by('-completed_at')
                    .first()
                )
                raw = session.raw_status if session and isinstance(session.raw_status, dict) else {}
                document = raw.get('document') if isinstance(raw.get('document'), dict) else {}
                user_details = raw.get('user_details') if isinstance(raw.get('user_details'), dict) else {}
                source = document or raw
                dob = extract_dob_from_raw(source) or parse_kyc_dob(user_details.get('dob'))
                persist_aadhaar_verified_identity(
                    kyc,
                    uid_masked=kyc.aadhaar or '',
                    name=str(source.get('name') or user_details.get('name') or ''),
                    dob=dob,
                    gender=str(source.get('gender') or user_details.get('gender') or ''),
                    provider_code=session.provider_code if session else 'cashfree_digilocker',
                    reference_id=str(source.get('reference_id') or session.reference_id if session else '') or '',
                    verified_at=kyc.aadhaar_verified_at or (session.completed_at if session else timezone.now()),
                    profile_updated=False,
                    raw=source if isinstance(source, dict) else None,
                    fill_gaps_only=True,
                )
                changed = True

            if changed:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'Backfilled verified_identity for {updated} user(s).'))
