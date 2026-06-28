"""
Resolve active bank account verification providers from ApiMaster configuration.
"""
from __future__ import annotations

from apps.core.utils import decrypt_secret_payload
from apps.integrations.banking.exceptions import BavConfigurationError
from apps.integrations.banking.providers.cashfree_bav import CashfreeBavProvider
from apps.integrations.kyc.cashfree_vrs_client import CashfreeVrsClient
from apps.integrations.models import ApiMaster

BANKING_PROVIDER_CODES = {
    'cashfree_bav': 'bav',
}


def _active_banking_master() -> ApiMaster:
    row = (
        ApiMaster.objects.filter(
            provider_type='banking',
            is_deleted=False,
            status__in=('active', 'sandbox'),
        )
        .order_by('-is_default', '-priority', 'pk')
        .first()
    )
    if not row:
        raise BavConfigurationError(
            'No active banking provider configured. '
            'In Admin → API Master → Banking, set status to active/sandbox, mark as default, and save credentials.'
        )
    return row


def _client_for_master(master: ApiMaster) -> CashfreeVrsClient:
    secrets = decrypt_secret_payload(master.secrets_encrypted or '')
    client_id = str(secrets.get('client_id') or '').strip()
    client_secret = str(secrets.get('client_secret') or '').strip()
    if not client_id or not client_secret:
        raise BavConfigurationError('Cashfree client_id and client_secret are required.')
    cfg = master.config_json if isinstance(master.config_json, dict) else {}
    timeout = int(cfg.get('timeout') or 15)
    return CashfreeVrsClient(
        base_url=master.base_url,
        client_id=client_id,
        client_secret=client_secret,
        timeout=timeout,
    )


def resolve_bav_provider() -> CashfreeBavProvider:
    master = _active_banking_master()
    if master.provider_code != 'cashfree_bav':
        raise BavConfigurationError(f'Unsupported banking provider: {master.provider_code}')
    return CashfreeBavProvider(master=master, client=_client_for_master(master))
