"""Resolve active AepsProviderConfig into a FingpayClient."""
from __future__ import annotations

from apps.core.utils import decrypt_secret_payload
from apps.integrations.fingpay.client import FingpayClient, FingpayClientError
from apps.integrations.fingpay.crypto import load_bundled_fingpay_certificate


def get_active_provider():
    from apps.aeps.models import AepsProviderConfig

    row = (
        AepsProviderConfig.objects.filter(is_active=True, is_deleted=False)
        .order_by('-updated_at')
        .first()
    )
    if not row:
        raise FingpayClientError('No active AEPS provider configured. Admin must save Fingpay credentials.')
    return row


def build_client_from_config(config) -> FingpayClient:
    secrets = decrypt_secret_payload(config.secrets_encrypted or '') or {}
    password = str(secrets.get('password') or '').strip()
    secret_key = str(secrets.get('secret_key') or '').strip()
    rsa_pem = str(secrets.get('rsa_public_key_pem') or secrets.get('public_key') or '').strip()
    if not rsa_pem:
        # Docs ship fingpay_public_production.cer — use as fallback for encryption
        rsa_pem = load_bundled_fingpay_certificate().strip()
    if not config.super_merchant_id or not config.super_merchant_login_id:
        raise FingpayClientError('Provider missing super merchant id / login id.')
    if not password:
        raise FingpayClientError('Provider password is required.')
    if not rsa_pem:
        raise FingpayClientError(
            'Provider RSA public certificate missing. Paste the Fingpay .cer PEM '
            '(BEGIN CERTIFICATE) or use Load bundled certificate in Admin.'
        )
    if not config.onboarding_base_url or not config.ekyc_base_url or not config.aeps_base_url:
        raise FingpayClientError('Provider base URLs incomplete.')
    return FingpayClient(
        super_merchant_id=config.super_merchant_id,
        super_merchant_login_id=config.super_merchant_login_id,
        password_plain=password,
        secret_key=secret_key,
        rsa_public_key_pem=rsa_pem,
        onboarding_base_url=config.onboarding_base_url,
        ekyc_base_url=config.ekyc_base_url,
        aeps_base_url=config.aeps_base_url,
        recon_base_url=config.recon_base_url or '',
        timeout=config.request_timeout_seconds or 180,
        onboarding_api_style=getattr(config, 'resolved_onboarding_api_style', None)
        or getattr(config, 'onboarding_api_style', None)
        or 'java',
        environment=getattr(config, 'environment', '') or '',
    )


def get_fingpay_client() -> FingpayClient:
    return build_client_from_config(get_active_provider())
