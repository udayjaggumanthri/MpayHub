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


def _persist_audit(
    *,
    endpoint: str,
    method: str,
    exchange: dict,
    success: bool,
    error_message: str = '',
    merchant_tran_id: str = '',
    user=None,
    debug_mode: bool = False,
) -> None:
    from apps.aeps.models import AepsApiAuditLog
    from apps.integrations.fingpay.crypto import scrub_sensitive

    resp = (exchange or {}).get('response') or {}
    req = (exchange or {}).get('request') or {}
    share = (exchange or {}).get('share_with_tapits') or {}
    http_status = resp.get('http_status')
    body = resp.get('body') if isinstance(resp.get('body'), dict) else {}
    provider_status = ''
    if isinstance(body, dict):
        provider_status = str(body.get('statusCode') or body.get('responseCode') or '')

    # Never persist multi-MB KYC base64 images in audit JSON — that OOMs workers
    # and makes onboarding appear stuck until the browser times out.
    plain_summary = scrub_sensitive(req.get('plain_json_scrubbed') or {}, for_tapits=False)
    body_summary = scrub_sensitive(body, for_tapits=False) if isinstance(body, (dict, list)) else {
        'raw': str(body)[:500]
    }

    kwargs = {
        'endpoint': (endpoint or '')[:255],
        'method': (method or 'POST')[:10],
        'merchant_tran_id': (merchant_tran_id or '')[:64],
        'user': user,
        'http_status': http_status,
        'provider_status_code': provider_status[:32],
        'latency_ms': resp.get('latency_ms'),
        'success': bool(success),
        'error_message': (error_message or '')[:500],
        'request_summary': {
            'url': req.get('url') or share.get('endpoint'),
            'mode': req.get('mode'),
            'headers': req.get('headers') or {},
            'plain': plain_summary,
        },
        'response_summary': {
            'http_status': http_status,
            'body': body_summary,
            'diagnosis': (exchange or {}).get('diagnosis') or '',
        },
        'debug_enabled': bool(debug_mode),
    }
    if debug_mode:
        raw_req = exchange.get('raw_request_body') or share.get('plain_json_request') or {}
        raw_resp = exchange.get('raw_response_body') or body or {}
        kwargs['request_headers'] = share.get('request_headers') or {}
        kwargs['request_body'] = scrub_sensitive(raw_req, for_tapits=False)
        kwargs['response_body'] = scrub_sensitive(raw_resp, for_tapits=False)
        # Store a scrubbed pack (image placeholders) so debug UI still works.
        kwargs['exchange_pack'] = scrub_sensitive(exchange or {}, for_tapits=False)
    AepsApiAuditLog.objects.create(**kwargs)


def build_client_from_config(config) -> FingpayClient:
    secrets = decrypt_secret_payload(config.secrets_encrypted or '') or {}
    password = str(secrets.get('password') or '').strip()
    password_mode = str(secrets.get('password_mode') or secrets.get('password_format') or 'plain').strip().lower()
    if password_mode not in ('plain', 'md5', 'hashed', 'hash', 'digest'):
        password_mode = 'plain'
    secret_key = str(secrets.get('secret_key') or '').strip()
    rsa_pem = str(secrets.get('rsa_public_key_pem') or secrets.get('public_key') or '').strip()

    api_mode = getattr(config, 'resolved_api_mode', None) or getattr(config, 'api_mode', None) or 'encrypted'
    if (getattr(config, 'environment', '') or '').lower() == 'simple':
        api_mode = 'simple'

    if not config.super_merchant_id or not config.super_merchant_login_id:
        raise FingpayClientError('Provider missing super merchant id / login id.')
    if not password:
        raise FingpayClientError('Provider password is required.')
    if not config.onboarding_base_url or not config.ekyc_base_url or not config.aeps_base_url:
        # Absolute full endpoints in endpoints_json can still work without bases,
        # but keep the guard soft only when at least create URL can resolve.
        eps = {}
        if hasattr(config, 'resolved_endpoints'):
            eps = config.resolved_endpoints() or {}
        has_abs_create = any(
            str(eps.get(k) or '').startswith('http')
            for k in ('onboarding_create_simple', 'onboarding_create_php', 'onboarding_create_java')
        )
        if not has_abs_create:
            raise FingpayClientError('Provider base URLs incomplete.')

    if api_mode == 'encrypted':
        if not rsa_pem:
            rsa_pem = load_bundled_fingpay_certificate().strip()
        if not rsa_pem:
            raise FingpayClientError(
                'Provider RSA public certificate missing. Paste the Fingpay .cer PEM '
                '(BEGIN CERTIFICATE) or use Load bundled certificate in Admin.'
            )
    else:
        if not secret_key:
            pass

    endpoints = {}
    if hasattr(config, 'resolved_endpoints'):
        endpoints = config.resolved_endpoints()
    elif getattr(config, 'endpoints_json', None):
        endpoints = config.endpoints_json

    # Pass the configured override only. The client resolves the effective
    # address (detection first) via `effective_egress_ip`.
    egress = (getattr(config, 'egress_ip', '') or '').strip()

    return FingpayClient(
        super_merchant_id=config.super_merchant_id,
        super_merchant_login_id=config.super_merchant_login_id,
        password_plain=password,
        password_mode=password_mode,
        secret_key=secret_key,
        rsa_public_key_pem=rsa_pem,
        onboarding_base_url=config.onboarding_base_url or '',
        ekyc_base_url=config.ekyc_base_url or '',
        aeps_base_url=config.aeps_base_url or '',
        recon_base_url=config.recon_base_url or '',
        timeout=config.request_timeout_seconds or 180,
        onboarding_api_style=getattr(config, 'resolved_onboarding_api_style', None)
        or getattr(config, 'onboarding_api_style', None)
        or 'java',
        environment=getattr(config, 'environment', '') or '',
        api_mode=api_mode,
        endpoints=endpoints,
        egress_ip=egress,
        debug_mode=bool(getattr(config, 'debug_mode', False)),
        audit_callback=_persist_audit,
        bank_list_url=getattr(config, 'bank_list_url', '') or '',
        aadhaar_pay_bank_list_url=getattr(config, 'aadhaar_pay_bank_list_url', '') or '',
    )


def get_fingpay_client() -> FingpayClient:
    return build_client_from_config(get_active_provider())
