"""
Resolve active payout providers from ApiMaster configuration.

Adding a second payout provider:
  1. Implement PayoutProvider in providers/<code>.py
  2. register_payout_provider('<code>', YourClass) (or add to PAYOUT_PROVIDER_CODES)
  3. Create ApiMaster row with provider_type=payout, provider_code=<code>
  4. Callback URL: /api/integrations/payout/<code>/callback/
"""
from __future__ import annotations

from apps.core.utils import decrypt_secret_payload
from apps.integrations.models import ApiMaster
from apps.integrations.payout.exceptions import PayoutConfigurationError
from apps.integrations.payout.port import PayoutProvider
from apps.integrations.payout.providers.vimopay import VimopayPayoutProvider

PAYOUT_PROVIDER_CODES: dict[str, type[PayoutProvider]] = {
    'vimopay': VimopayPayoutProvider,
}


def register_payout_provider(code: str, cls: type[PayoutProvider]) -> None:
    """Plug-in registration for future payout providers (no domain changes required)."""
    key = (code or '').strip().lower()
    if not key:
        raise ValueError('provider code is required')
    if not issubclass(cls, PayoutProvider):
        raise TypeError('cls must subclass PayoutProvider')
    PAYOUT_PROVIDER_CODES[key] = cls


def list_registered_payout_providers() -> list[str]:
    return sorted(PAYOUT_PROVIDER_CODES.keys())


def _active_payout_master(*, provider_code: str | None = None) -> ApiMaster:
    qs = ApiMaster.objects.filter(
        provider_type='payout',
        is_deleted=False,
        status__in=('active', 'sandbox'),
    )
    if provider_code:
        qs = qs.filter(provider_code=provider_code)
    row = qs.order_by('-is_default', '-priority', 'pk').first()
    if not row:
        raise PayoutConfigurationError(
            'No active payout provider configured. '
            'In Admin → API Master → Payout, set status to active/sandbox, mark as default, '
            'and save provider credentials.'
        )
    return row


def build_payout_provider(master: ApiMaster) -> PayoutProvider:
    """Instantiate adapter for a specific ApiMaster row (e.g. admin test_connection)."""
    code = (master.provider_code or '').strip().lower()
    cls = PAYOUT_PROVIDER_CODES.get(code)
    if cls is None:
        raise PayoutConfigurationError(f'Unsupported payout provider: {master.provider_code}')
    secrets = decrypt_secret_payload(master.secrets_encrypted or '')
    return cls(master=master, secrets=secrets)


def resolve_payout_provider(*, provider_code: str | None = None) -> PayoutProvider:
    master = _active_payout_master(provider_code=provider_code)
    return build_payout_provider(master)


def resolve_payout_provider_for_callback(*, provider_code: str = 'vimopay') -> PayoutProvider:
    """Prefer exact provider_code for webhook routing; fall back to active default."""
    try:
        return resolve_payout_provider(provider_code=provider_code)
    except PayoutConfigurationError:
        return resolve_payout_provider()
