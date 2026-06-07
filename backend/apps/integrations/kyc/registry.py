"""
Resolve active KYC providers from ApiMaster configuration.
"""
from __future__ import annotations

from apps.core.utils import decrypt_secret_payload
from apps.integrations.kyc.cashfree_vrs_client import CashfreeVrsClient
from apps.integrations.kyc.exceptions import KycConfigurationError
from apps.integrations.kyc.providers.cashfree_digilocker import CashfreeDigilockerProvider
from apps.integrations.kyc.providers.cashfree_pan import CashfreePanProvider
from apps.integrations.models import ApiMaster

KYC_PROVIDER_CODES = {
    'cashfree_pan': 'pan',
    'cashfree_digilocker': 'aadhaar',
}


def _active_kyc_master(*, kyc_service: str) -> ApiMaster:
    base = ApiMaster.objects.filter(
        provider_type='kyc',
        is_deleted=False,
        status__in=('active', 'sandbox'),
    )
    row = (
        base.filter(kyc_service=kyc_service)
        .order_by('-is_default', '-priority', 'pk')
        .first()
    )
    if not row:
        code_by_service = {v: k for k, v in KYC_PROVIDER_CODES.items()}
        provider_code = code_by_service.get(kyc_service, '')
        if provider_code:
            row = (
                base.filter(provider_code=provider_code)
                .order_by('-is_default', '-priority', 'pk')
                .first()
            )
    if not row:
        raise KycConfigurationError(
            f'No active KYC provider configured for {kyc_service}. '
            'In Admin → API Master, set status to active/sandbox, mark as default, and save credentials.'
        )
    return row


def _client_for_master(master: ApiMaster) -> CashfreeVrsClient:
    secrets = decrypt_secret_payload(master.secrets_encrypted or '')
    client_id = str(secrets.get('client_id') or '').strip()
    client_secret = str(secrets.get('client_secret') or '').strip()
    if not client_id or not client_secret:
        raise KycConfigurationError('Cashfree client_id and client_secret are required.')
    cfg = master.config_json if isinstance(master.config_json, dict) else {}
    timeout = int(cfg.get('timeout') or 15)
    return CashfreeVrsClient(
        base_url=master.base_url,
        client_id=client_id,
        client_secret=client_secret,
        timeout=timeout,
    )


def resolve_pan_provider() -> CashfreePanProvider:
    master = _active_kyc_master(kyc_service='pan')
    if master.provider_code != 'cashfree_pan':
        raise KycConfigurationError(f'Unsupported PAN provider: {master.provider_code}')
    return CashfreePanProvider(master=master, client=_client_for_master(master))


def resolve_aadhaar_provider() -> CashfreeDigilockerProvider:
    master = _active_kyc_master(kyc_service='aadhaar')
    if master.provider_code != 'cashfree_digilocker':
        raise KycConfigurationError(f'Unsupported Aadhaar provider: {master.provider_code}')
    return CashfreeDigilockerProvider(master=master, client=_client_for_master(master))


def infer_kyc_service(provider_code: str) -> str:
    return KYC_PROVIDER_CODES.get(str(provider_code or '').strip().lower(), '')
