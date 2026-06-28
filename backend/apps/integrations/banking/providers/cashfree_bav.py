from __future__ import annotations

from apps.integrations.banking.exceptions import BavVerificationFailed
from apps.integrations.banking.types import BavVerifyResult
from apps.integrations.kyc.cashfree_vrs_client import CashfreeVrsClient
from apps.integrations.models import ApiMaster


def _resolve_ifsc(raw: dict, submitted_ifsc: str) -> str:
    submitted = submitted_ifsc.upper().strip()
    ifsc_details = raw.get('ifsc_details')
    if isinstance(ifsc_details, dict):
        returned = str(ifsc_details.get('ifsc') or '').upper().strip()
        if returned:
            return returned
    top_level = str(raw.get('ifsc') or '').upper().strip()
    if top_level:
        return top_level
    return submitted


class CashfreeBavProvider:
    def __init__(self, *, master: ApiMaster, client: CashfreeVrsClient):
        self.master = master
        self.client = client
        self.config = master.config_json if isinstance(master.config_json, dict) else {}

    @property
    def provider_code(self) -> str:
        return self.master.provider_code

    def _use_mock(self) -> bool:
        if self.master.status != 'sandbox':
            return False
        return bool(self.config.get('use_mock'))

    def _mock_result(self, *, account_number: str, ifsc: str) -> BavVerifyResult:
        return BavVerifyResult(
            success=True,
            beneficiary_name='SANDBOX BENEFICIARY',
            bank_name='SANDBOX BANK',
            branch='SANDBOX BRANCH',
            city='SANDBOX',
            ifsc=ifsc.upper().strip(),
            account_status='VALID',
            account_status_code='ACCOUNT_IS_VALID',
            name_match_score='',
            name_match_result='',
            reference_id='mock-ref',
            utr='',
            raw={'mock': True, 'account_number': account_number, 'ifsc': ifsc},
        )

    def verify(
        self,
        *,
        user,
        account_number: str,
        ifsc: str,
        name: str = '',
        phone: str = '',
    ) -> BavVerifyResult:
        del user, name
        if self._use_mock():
            return self._mock_result(account_number=account_number, ifsc=ifsc)

        raw = self.client.verify_bank_account_sync(
            bank_account=account_number,
            ifsc=ifsc,
            phone=phone,
        )
        account_status = str(raw.get('account_status') or '').upper()
        account_status_code = str(raw.get('account_status_code') or '').upper()
        if account_status != 'VALID' or account_status_code != 'ACCOUNT_IS_VALID':
            message = str(
                raw.get('message')
                or raw.get('account_status_message')
                or 'Bank account validation failed. Please check account number and IFSC.'
            )
            raise BavVerificationFailed(message, code=account_status_code or 'invalid_account', details=raw)

        resolved_ifsc = _resolve_ifsc(raw, ifsc)
        beneficiary_name = str(raw.get('name_at_bank') or raw.get('beneficiary_name') or '').strip()
        if not beneficiary_name:
            raise BavVerificationFailed(
                'Bank account validated but beneficiary name was not returned.',
                code='missing_beneficiary_name',
                details=raw,
            )

        bank_name = str(raw.get('bank_name') or '').strip()
        if not bank_name:
            ifsc_details = raw.get('ifsc_details')
            if isinstance(ifsc_details, dict):
                bank_name = str(ifsc_details.get('bank') or '').strip()

        return BavVerifyResult(
            success=True,
            beneficiary_name=beneficiary_name,
            bank_name=bank_name,
            branch=str(raw.get('branch') or '').strip(),
            city=str(raw.get('city') or '').strip(),
            ifsc=resolved_ifsc,
            account_status=account_status,
            account_status_code=account_status_code,
            name_match_score=str(raw.get('name_match_score') or ''),
            name_match_result=str(raw.get('name_match_result') or ''),
            reference_id=str(raw.get('reference_id') or ''),
            utr=str(raw.get('utr') or ''),
            raw=raw,
        )
