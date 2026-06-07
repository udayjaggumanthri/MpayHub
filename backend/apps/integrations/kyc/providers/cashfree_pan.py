from __future__ import annotations

import re

from apps.integrations.kyc.cashfree_vrs_client import CashfreeVrsClient
from apps.integrations.kyc.exceptions import KycVerificationFailed
from apps.integrations.kyc.types import PanVerifyResult
from apps.integrations.kyc.verification_id import new_cashfree_verification_id
from apps.integrations.models import ApiMaster


def _normalize_pan_name(value: str) -> str:
    """Collapse whitespace and compare case-insensitively (John Doe == JOHN DOE)."""
    return re.sub(r'\s+', ' ', str(value or '').strip().upper())


class CashfreePanProvider:
    def __init__(self, *, master: ApiMaster, client: CashfreeVrsClient):
        self.master = master
        self.client = client
        self.config = master.config_json if isinstance(master.config_json, dict) else {}

    @property
    def provider_code(self) -> str:
        return self.master.provider_code

    def _mode(self) -> str:
        return str(self.config.get('mode') or 'sync').strip().lower()

    def _name_match_hint(self, raw: dict) -> str:
        registered = self._registered_name(raw)
        if registered:
            return f' Name on PAN card: {registered}.'
        return ''

    def _registered_name(self, raw: dict) -> str:
        return str(raw.get('registered_name') or raw.get('name_pan_card') or '').strip()

    def _names_match(self, submitted_name: str, raw: dict) -> bool:
        registered = self._registered_name(raw)
        if not submitted_name or not registered:
            return False
        return _normalize_pan_name(submitted_name) == _normalize_pan_name(registered)

    def _accept_name_match(self, raw: dict, *, submitted_name: str = '') -> None:
        if self._names_match(submitted_name, raw):
            return

        registered = self._registered_name(raw)
        if registered and submitted_name:
            raise KycVerificationFailed(
                'Name on PAN does not match records. Enter your full name exactly as printed on your PAN card.'
                + self._name_match_hint(raw),
                code='name_match_failed',
                details=raw,
            )

        min_score = self.config.get('min_name_match_score')
        if min_score is None:
            return
        try:
            score = float(raw.get('name_match_score') or 0)
        except (TypeError, ValueError):
            score = 0.0
        if score < float(min_score):
            raise KycVerificationFailed(
                'Name on PAN does not match records. Enter your full name exactly as printed on your PAN card.'
                + self._name_match_hint(raw),
                code='name_match_failed',
                details=raw,
            )
        allowed = self.config.get('accept_name_match_results')
        if isinstance(allowed, list) and allowed:
            result = str(raw.get('name_match_result') or '').strip().upper()
            norm = {str(x).strip().upper() for x in allowed}
            if result and result not in norm:
                raise KycVerificationFailed(
                    'Name on PAN does not match records. Enter your full name exactly as printed on your PAN card.'
                    + self._name_match_hint(raw),
                    code='name_match_result',
                    details=raw,
                )

    def verify_pan(self, *, user, pan: str, name: str) -> PanVerifyResult:
        mode = self._mode()
        verification_id = ''
        if mode == 'advance':
            verification_id = new_cashfree_verification_id('PAN', user)
            raw = self.client.verify_pan_advance(
                pan=pan,
                name=name,
                verification_id=verification_id,
            )
            ok = str(raw.get('status') or '').upper() == 'VALID'
            if not ok:
                raise KycVerificationFailed(
                    str(raw.get('message') or 'PAN verification failed.'),
                    code=str(raw.get('status') or 'invalid'),
                    details=raw,
                )
            self._accept_name_match(raw, submitted_name=name)
            return PanVerifyResult(
                success=True,
                pan=pan,
                registered_name=self._registered_name(raw),
                reference_id=str(raw.get('reference_id') or ''),
                verification_id=verification_id,
                status=str(raw.get('status') or ''),
                message=str(raw.get('message') or ''),
                raw=raw,
            )

        raw = self.client.verify_pan_sync(pan=pan, name=name)
        if not raw.get('valid'):
            raise KycVerificationFailed(
                str(raw.get('message') or 'PAN verification failed.'),
                code='invalid_pan',
                details=raw,
            )
        self._accept_name_match(raw, submitted_name=name)
        return PanVerifyResult(
            success=True,
            pan=pan,
            registered_name=self._registered_name(raw),
            date_of_birth=str(raw.get('dob') or raw.get('date_of_birth') or ''),
            pan_type=str(raw.get('type') or ''),
            reference_id=str(raw.get('reference_id') or ''),
            verification_id=verification_id,
            status='VALID' if raw.get('valid') else 'INVALID',
            message=str(raw.get('message') or ''),
            raw=raw,
        )
