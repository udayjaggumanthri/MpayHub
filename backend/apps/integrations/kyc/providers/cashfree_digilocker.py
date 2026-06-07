from __future__ import annotations

import re

from django.utils import timezone

from apps.integrations.kyc.cashfree_vrs_client import CashfreeVrsClient
from apps.integrations.kyc.verification_id import new_cashfree_verification_id
from apps.integrations.kyc.exceptions import KycVerificationFailed
from apps.integrations.kyc.types import DigilockerDocumentResult, DigilockerInitResult, DigilockerStatusResult
from apps.integrations.models import ApiMaster
from apps.users.models import KycDigilockerSession


def _new_verification_id(user) -> str:
    return new_cashfree_verification_id('DL', user)


def _mask_uid(value: str) -> str:
    s = re.sub(r'\D', '', str(value or ''))
    if len(s) >= 4:
        return f'XXXX{s[-4:]}'
    return str(value or '').strip()


class CashfreeDigilockerProvider:
    def __init__(self, *, master: ApiMaster, client: CashfreeVrsClient):
        self.master = master
        self.client = client
        self.config = master.config_json if isinstance(master.config_json, dict) else {}

    @property
    def provider_code(self) -> str:
        return self.master.provider_code

    def _redirect_url(self) -> str:
        return str(self.config.get('redirect_url') or '').strip()

    def _documents(self) -> list[str]:
        docs = self.config.get('document_requested')
        if isinstance(docs, list) and docs:
            return [str(d).upper() for d in docs]
        return ['AADHAAR']

    def _user_flow(self) -> str:
        return str(self.config.get('user_flow') or 'signup').strip().lower()

    def init_session(self, *, user, aadhaar_number: str | None = None) -> DigilockerInitResult:
        verification_id = _new_verification_id(user)
        if aadhaar_number:
            self.client.digilocker_verify_account(
                verification_id=verification_id,
                aadhaar_number=str(aadhaar_number).strip(),
            )
        raw = self.client.digilocker_create_url(
            verification_id=verification_id,
            document_requested=self._documents(),
            redirect_url=self._redirect_url(),
            user_flow=self._user_flow(),
        )
        KycDigilockerSession.objects.create(
            user=user,
            verification_id=verification_id,
            reference_id=str(raw.get('reference_id') or ''),
            status=str(raw.get('status') or 'PENDING'),
            user_flow=str(raw.get('user_flow') or self._user_flow()),
            document_requested=self._documents(),
            provider_code=self.provider_code,
            raw_status=raw,
        )
        return DigilockerInitResult(
            verification_id=verification_id,
            reference_id=str(raw.get('reference_id') or ''),
            url=str(raw.get('url') or ''),
            status=str(raw.get('status') or 'PENDING'),
            user_flow=str(raw.get('user_flow') or ''),
            raw=raw,
        )

    def get_status(self, *, verification_id: str) -> DigilockerStatusResult:
        raw = self.client.digilocker_get_status(verification_id=verification_id)
        status = str(raw.get('status') or 'PENDING')
        session = KycDigilockerSession.objects.filter(verification_id=verification_id, is_deleted=False).first()
        if session:
            session.status = status
            session.reference_id = str(raw.get('reference_id') or session.reference_id or '')
            session.raw_status = raw
            session.save(update_fields=['status', 'reference_id', 'raw_status', 'updated_at'])
        return DigilockerStatusResult(
            verification_id=verification_id,
            status=status,
            reference_id=str(raw.get('reference_id') or ''),
            user_details=raw.get('user_details') if isinstance(raw.get('user_details'), dict) else {},
            document_consent=raw.get('document_consent') if isinstance(raw.get('document_consent'), list) else [],
            raw=raw,
        )

    def fetch_document(self, *, verification_id: str, document_type: str = 'AADHAAR') -> DigilockerDocumentResult:
        raw = self.client.digilocker_get_document(
            document_type=document_type.upper(),
            verification_id=verification_id,
        )
        uid = str(raw.get('uid') or '')
        return DigilockerDocumentResult(
            verification_id=verification_id,
            status=str(raw.get('status') or ''),
            uid_masked=_mask_uid(uid),
            name=str(raw.get('name') or ''),
            date_of_birth=str(raw.get('dob') or raw.get('date_of_birth') or ''),
            gender=str(raw.get('gender') or ''),
            raw=raw,
        )

    def complete_if_authenticated(self, *, user, verification_id: str) -> DigilockerDocumentResult:
        status = self.get_status(verification_id=verification_id)
        if status.status not in ('AUTHENTICATED', 'SUCCESS'):
            raise KycVerificationFailed(
                f'DigiLocker verification is not complete (status: {status.status}).',
                code=status.status.lower(),
                details=status.raw,
            )
        doc = self.fetch_document(verification_id=verification_id, document_type='AADHAAR')
        if str(doc.status or '').upper() not in ('SUCCESS', 'VALID', ''):
            if not doc.uid_masked:
                raise KycVerificationFailed(
                    str(doc.raw.get('message') or 'Could not retrieve Aadhaar from DigiLocker.'),
                    code='document_fetch_failed',
                    details=doc.raw,
                )
        session = KycDigilockerSession.objects.filter(
            user=user,
            verification_id=verification_id,
            is_deleted=False,
        ).first()
        if session:
            raw_status = dict(session.raw_status or {})
            if isinstance(doc.raw, dict):
                raw_status['document'] = doc.raw
            update_fields = ['raw_status', 'updated_at']
            if not session.completed_at:
                session.completed_at = timezone.now()
                session.status = 'AUTHENTICATED'
                update_fields.extend(['completed_at', 'status'])
            session.raw_status = raw_status
            session.save(update_fields=update_fields)
        return doc
