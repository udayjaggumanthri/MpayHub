"""AEPS HTTP API — entitlement, onboarding, products, reports, webhooks."""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.aeps.models import AepsAccessRequest, AepsEntitlement, AepsMerchantProfile, AepsProviderConfig, AepsReconBatch
from apps.aeps.services import entitlement as entitlement_svc
from apps.aeps.services import onboarding as onboarding_svc
from apps.aeps.services import products as products_svc
from apps.aeps.services import recon as recon_svc
from apps.aeps.services import reports as reports_svc
from apps.aeps.services.gates import me_status_payload
from apps.core.utils import decrypt_secret_payload, encrypt_secret_payload
from apps.integrations.fingpay.endpoints import (
    DEFAULT_EGRESS_IP,
    ENDPOINT_FIELD_META,
    URL_PRESETS,
    default_endpoints_for,
    expand_endpoints_to_full_urls,
)
from apps.session_security.services.ip import get_client_ip


def _ok(data=None, message='', http_status=200):
    return Response({'success': True, 'message': message, 'data': data or {}}, status=http_status)


def _flatten_exc_message(exc) -> str:
    """Turn DRF ValidationError / PermissionDenied detail into a plain string."""
    detail = getattr(exc, 'detail', None)
    if detail is None:
        return str(exc)

    def _one(val) -> str:
        if isinstance(val, (list, tuple)):
            return ', '.join(_one(x) for x in val)
        if isinstance(val, dict):
            if val.get('message') is not None:
                return _one(val.get('message'))
            return '; '.join(f'{k}: {_one(v)}' for k, v in val.items() if k != 'code')
        return str(val)

    if isinstance(detail, dict):
        if detail.get('message') is not None:
            return _one(detail.get('message'))
        return _one(detail)
    if isinstance(detail, (list, tuple)):
        return _one(detail)
    return str(detail)


def _err(message, *, code=None, http_status=400, errors=None, data=None):
    body = {'success': False, 'message': str(message)}
    if code:
        body['code'] = code
    if errors:
        body['errors'] = errors
    if data is not None:
        body['data'] = data
    return Response(body, status=http_status)


def _exc_exchange(exc):
    # Preferred: attribute attached by the service (preserves int/bool/float types,
    # unlike ValidationError detail which DRF stringifies recursively).
    raw = None
    if hasattr(exc, 'fingpay_exchange'):
        raw = getattr(exc, 'fingpay_exchange', None)
    else:
        detail = getattr(exc, 'detail', None)
        if isinstance(detail, dict) and 'fingpay_exchange' in detail:
            raw = detail.get('fingpay_exchange')
    if raw is None:
        return None
    # Strip multi-MB KYC images so the API error response stays small and the UI
    # does not hang while JSON-serializing a failed onboarding pack.
    from apps.integrations.fingpay.crypto import scrub_sensitive

    return scrub_sensitive(raw, for_tapits=False)


def _require_admin(request):
    return getattr(request.user, 'role', None) == 'Admin'


def _geo(request):
    data = request.data if hasattr(request, 'data') else {}
    lat = data.get('latitude')
    lng = data.get('longitude')
    try:
        lat = float(lat) if lat is not None else None
        lng = float(lng) if lng is not None else None
    except (TypeError, ValueError):
        lat = lng = None
    return lat, lng


# ----- me / access -----


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_status(request):
    return _ok(me_status_payload(request.user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def access_request_create(request):
    try:
        row = entitlement_svc.create_access_request(user=request.user, reason=request.data.get('reason') or '')
    except Exception as exc:
        code = None
        detail = getattr(exc, 'detail', None)
        if isinstance(detail, dict):
            code = detail.get('code')
        return _err(_flatten_exc_message(exc), code=code, http_status=400)
    return _ok({'id': row.pk, 'status': row.status}, message='Access request submitted')


# ----- Admin provider / entitlements -----

SERVER_EGRESS_IP = DEFAULT_EGRESS_IP

ENV_PRESETS = {
    'uat': {
        'name': 'fingpay-uat',
        'environment': 'uat',
        'api_mode': 'encrypted',
        **URL_PRESETS['uat'],
    },
    'prod': {
        'name': 'fingpay-prod',
        'environment': 'prod',
        'api_mode': 'encrypted',
        **URL_PRESETS['prod'],
    },
    'simple': {
        'name': 'fingpay-simple',
        'environment': 'simple',
        'api_mode': 'simple',
        **URL_PRESETS['simple'],
    },
}


def _normalize_env(raw: str) -> str:
    env = (raw or '').strip().lower()
    if env in ('uat', 'prod', 'simple'):
        return env
    return 'prod'


def _onboarding_endpoint_catalog() -> list[dict]:
    """Activatable onboarding profiles — only one live-active at a time."""
    from apps.aeps.models import AepsProviderConfig

    catalog = []
    active = (
        AepsProviderConfig.objects.filter(is_active=True, is_deleted=False)
        .order_by('-updated_at')
        .first()
    )
    active_env = active.environment if active else None
    active_style = active.resolved_onboarding_api_style if active else None
    for env in ('uat', 'prod', 'simple'):
        preset = ENV_PRESETS[env]
        row = (
            AepsProviderConfig.objects.filter(environment=env, is_deleted=False)
            .order_by('-is_active', '-updated_at')
            .first()
        )
        base = (row.onboarding_base_url if row else '') or preset['onboarding_base_url']
        base = base.rstrip('/')
        if env == 'simple':
            path = AepsProviderConfig.ONBOARDING_CREATE_PATHS['simple']
            if row:
                path = row.onboarding_create_path()
            catalog.append(
                {
                    'id': 'simple',
                    'environment': 'simple',
                    'style': 'simple',
                    'label': 'Simple API (plain JSON)',
                    'endpoint': f'{base}{path}',
                    'aes_mode': 'none',
                    'api_mode': 'simple',
                    'configured': bool(row and (row.super_merchant_login_id or row.secrets_encrypted)),
                    'is_active': bool(active_env == 'simple'),
                    'stored_on_env': True,
                }
            )
            continue
        stored_style = (row.resolved_onboarding_api_style if row else 'java')
        for style, label in (('java', 'Java / .NET'), ('php', 'PHP')):
            path = AepsProviderConfig.ONBOARDING_CREATE_PATHS[style]
            catalog.append(
                {
                    'id': f'{env}-{style}',
                    'environment': env,
                    'style': style,
                    'label': f'{env.upper()} · {label}',
                    'endpoint': f'{base}{path}',
                    'aes_mode': 'cbc' if style == 'php' else 'ecb',
                    'api_mode': 'encrypted',
                    'configured': bool(row and (row.super_merchant_login_id or row.secrets_encrypted)),
                    'is_active': bool(active_env == env and active_style == style),
                    'stored_on_env': stored_style == style,
                }
            )
    return catalog


def _serialize_provider_row(row, *, bundled_cert: str = '') -> dict:
    secrets = decrypt_secret_payload(row.secrets_encrypted or '') or {} if row else {}
    style = row.resolved_onboarding_api_style if row else 'java'
    api_mode = row.resolved_api_mode if row else 'encrypted'
    egress = row.resolved_egress_ip() if row else DEFAULT_EGRESS_IP
    endpoints = row.resolved_endpoints() if row else default_endpoints_for(environment='prod')
    password_mode = str(secrets.get('password_mode') or 'plain').lower()
    if password_mode not in ('plain', 'md5'):
        password_mode = 'plain'
    full_endpoints = expand_endpoints_to_full_urls(
        endpoints,
        onboarding_base_url=row.onboarding_base_url if row else '',
        ekyc_base_url=row.ekyc_base_url if row else '',
        aeps_base_url=row.aeps_base_url if row else '',
        recon_base_url=row.recon_base_url if row else '',
    )
    return {
        'id': row.pk if row else None,
        'configured': bool(row),
        'name': row.name if row else '',
        'environment': row.environment if row else 'prod',
        'is_active': bool(row and row.is_active),
        'api_mode': api_mode,
        'debug_mode': bool(row and row.debug_mode),
        'egress_ip': egress,
        'endpoints_json': endpoints,
        'full_endpoints': full_endpoints,
        'endpoint_fields': ENDPOINT_FIELD_META,
        'password_mode': password_mode,
        'onboarding_api_style': style,
        'onboarding_create_url': row.onboarding_create_url() if row else '',
        'onboarding_aes_mode': row.onboarding_aes_mode() if row else 'ecb',
        'super_merchant_id': row.super_merchant_id if row else '',
        'super_merchant_login_id': row.super_merchant_login_id if row else '',
        'onboarding_base_url': row.onboarding_base_url if row else '',
        'ekyc_base_url': row.ekyc_base_url if row else '',
        'aeps_base_url': row.aeps_base_url if row else '',
        'recon_base_url': row.recon_base_url if row else '',
        'bank_list_url': row.bank_list_url if row else '',
        'aadhaar_pay_bank_list_url': row.aadhaar_pay_bank_list_url if row else '',
        'request_timeout_seconds': row.request_timeout_seconds if row else 180,
        'notes': row.notes if row else '',
        'has_password': bool(secrets.get('password')),
        'has_secret_key': bool(secrets.get('secret_key')),
        'has_public_key': bool(secrets.get('rsa_public_key_pem') or secrets.get('public_key')),
        'gstin_number': secrets.get('gstin_number') or secrets.get('gstinNumber') or '',
        'company_or_shop_pan': secrets.get('company_or_shop_pan')
        or secrets.get('companyOrShopPan')
        or '',
        'server_egress_ip': egress,
        'whitelist_note': (
            f'Share ONLY this server IP with Tapits for whitelist: {egress}. '
            'Do not use old AWS EC2 IPs from other portals.'
        ),
        'bundled_public_certificate': bundled_cert,
        'has_bundled_certificate': bool(bundled_cert),
        'onboarding_endpoints': _onboarding_endpoint_catalog(),
        'hash_help': {
            'simple_onboarding': "Base64(SHA256(login + '@' + MD5(password)))",
            'simple_txn': 'Base64(SHA256(plainJson + secretKey + trnTimestamp)) — trnTimestamp format YYYY-MM-DD HH:MM:SS',
            'encrypted': 'Base64(SHA256(plain JSON)) + RSA eskey',
            'password_plain': 'Store plain password — app MD5-hashes it for Fingpay body/hash',
            'password_md5': 'Store 32-char MD5 hex — used as-is (no second hash)',
        },
    }


def _get_or_create_env_row(environment: str) -> AepsProviderConfig:
    env = _normalize_env(environment)
    preset = ENV_PRESETS[env]
    row = (
        AepsProviderConfig.objects.filter(environment=env, is_deleted=False)
        .order_by('-is_active', '-updated_at')
        .first()
    )
    if row:
        return row
    # Migrate legacy single "default" row into prod once
    if env == 'prod':
        legacy = (
            AepsProviderConfig.objects.filter(is_deleted=False)
            .exclude(environment__in=('uat', 'simple'))
            .order_by('-is_active', '-updated_at')
            .first()
        )
        if legacy:
            legacy.name = preset['name']
            legacy.environment = 'prod'
            legacy.save(update_fields=['name', 'environment', 'updated_at'])
            return legacy
    return AepsProviderConfig(
        name=preset['name'],
        environment=env,
        api_mode=preset.get('api_mode') or ('simple' if env == 'simple' else 'encrypted'),
        onboarding_base_url=preset['onboarding_base_url'],
        ekyc_base_url=preset['ekyc_base_url'],
        aeps_base_url=preset['aeps_base_url'],
        recon_base_url=preset.get('recon_base_url') or '',
        bank_list_url=preset['bank_list_url'],
        aadhaar_pay_bank_list_url=preset['aadhaar_pay_bank_list_url'],
        egress_ip=DEFAULT_EGRESS_IP,
        endpoints_json=default_endpoints_for(
            environment=env,
            onboarding_api_style='php' if env != 'simple' else 'php',
        ),
        is_active=False,
    )


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def admin_provider_config(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    from apps.integrations.fingpay.crypto import load_bundled_fingpay_certificate

    bundled_cert = load_bundled_fingpay_certificate()
    env = _normalize_env(
        request.query_params.get('environment') or (request.data.get('environment') if hasattr(request, 'data') else '') or ''
    )
    if not (request.query_params.get('environment') or (getattr(request, 'data', None) or {}).get('environment')):
        active = AepsProviderConfig.objects.filter(is_active=True, is_deleted=False).order_by('-updated_at').first()
        env = _normalize_env(active.environment if active else 'prod')

    if request.method == 'GET':
        row = (
            AepsProviderConfig.objects.filter(environment=env, is_deleted=False)
            .order_by('-is_active', '-updated_at')
            .first()
        )
        if not row and env == 'prod':
            row = AepsProviderConfig.objects.filter(is_deleted=False).order_by('-is_active', '-updated_at').first()
        envs = []
        for e in ('uat', 'prod', 'simple'):
            r = AepsProviderConfig.objects.filter(environment=e, is_deleted=False).order_by('-is_active', '-updated_at').first()
            envs.append(
                {
                    'environment': e,
                    'configured': bool(r and (r.super_merchant_login_id or r.secrets_encrypted)),
                    'is_active': bool(r and r.is_active),
                    'api_mode': r.resolved_api_mode if r else ('simple' if e == 'simple' else 'encrypted'),
                    'debug_mode': bool(r and r.debug_mode),
                    'onboarding_api_style': r.resolved_onboarding_api_style if r else ('simple' if e == 'simple' else 'java'),
                    'onboarding_create_url': r.onboarding_create_url() if r else '',
                    'super_merchant_id': r.super_merchant_id if r else '',
                    'super_merchant_login_id': r.super_merchant_login_id if r else '',
                    'egress_ip': r.resolved_egress_ip() if r else DEFAULT_EGRESS_IP,
                }
            )
        payload = _serialize_provider_row(row, bundled_cert=bundled_cert)
        payload['environments'] = envs
        payload['presets'] = ENV_PRESETS
        payload['default_endpoints'] = {
            e: default_endpoints_for(environment=e, onboarding_api_style='php') for e in ('uat', 'prod', 'simple')
        }
        payload['credential_help'] = {
            'public_certificate': (
                'Use fingpay_public_production.cer from AEPS docs '
                '(-----BEGIN CERTIFICATE-----). Same file is bundled for one-click load. '
                'Not required for Simple API profile.'
            ),
            'secret_key': (
                'Issued by Fingpay Integration Team — required for Simple txn/eKYC/2FA hashes and 3-way recon.'
            ),
            'encryption': (
                'UAT/Production: Java AES-128-ECB or PHP AES-128-CBC. '
                'Simple API: plain JSON, no eskey. Activate exactly one profile for all users.'
            ),
            'onboarding_paths': AepsProviderConfig.ONBOARDING_CREATE_PATHS,
        }
        return _ok(payload)

    data = request.data or {}
    env = _normalize_env(str(data.get('environment') or env))
    row = _get_or_create_env_row(env)
    preset = ENV_PRESETS[env]
    for field in (
        'super_merchant_id',
        'super_merchant_login_id',
        'onboarding_base_url',
        'ekyc_base_url',
        'aeps_base_url',
        'recon_base_url',
        'bank_list_url',
        'aadhaar_pay_bank_list_url',
        'notes',
        'egress_ip',
    ):
        if field in data:
            setattr(row, field, data.get(field) or '')
    if env == 'simple':
        row.api_mode = 'simple'
        row.onboarding_api_style = 'java'  # unused for simple; create path uses simple key
    else:
        if 'api_mode' in data:
            mode = str(data.get('api_mode') or 'encrypted').lower()
            row.api_mode = mode if mode in ('encrypted', 'simple') else 'encrypted'
        if 'onboarding_api_style' in data or data.get('activate_onboarding_style'):
            style = str(
                data.get('activate_onboarding_style') or data.get('onboarding_api_style') or row.onboarding_api_style or 'java'
            ).lower()
            if style not in ('java', 'php'):
                return _err('onboarding_api_style must be java or php', http_status=400)
            row.onboarding_api_style = style
            row.api_mode = 'encrypted'
    if 'debug_mode' in data:
        row.debug_mode = bool(data.get('debug_mode'))
    if 'endpoints_json' in data and isinstance(data.get('endpoints_json'), dict):
        row.endpoints_json = data.get('endpoints_json') or {}
    elif 'full_endpoints' in data and isinstance(data.get('full_endpoints'), dict):
        # Admin may paste absolute module URLs from the Fingpay doc (often production).
        cleaned = {}
        for k, v in (data.get('full_endpoints') or {}).items():
            if v is not None and str(v).strip():
                cleaned[str(k)] = str(v).strip()
        if cleaned:
            row.endpoints_json = cleaned
    elif data.get('reset_endpoints'):
        row.endpoints_json = default_endpoints_for(
            environment=env,
            onboarding_api_style=row.onboarding_api_style or 'php',
        )
    row.name = preset['name']
    row.environment = env
    for url_field in (
        'onboarding_base_url',
        'ekyc_base_url',
        'aeps_base_url',
        'bank_list_url',
        'aadhaar_pay_bank_list_url',
    ):
        if not getattr(row, url_field):
            setattr(row, url_field, preset.get(url_field) or '')
    if not row.egress_ip:
        row.egress_ip = DEFAULT_EGRESS_IP
    if 'request_timeout_seconds' in data:
        row.request_timeout_seconds = int(data.get('request_timeout_seconds') or 180)
    activate = bool(data.get('is_active')) if 'is_active' in data else bool(data.get('activate'))
    activate = activate or bool(data.get('make_active')) or bool(data.get('activate_onboarding_style'))
    if activate:
        AepsProviderConfig.objects.filter(is_deleted=False, is_active=True).update(is_active=False)
        row.is_active = True
    elif 'is_active' in data:
        row.is_active = bool(data.get('is_active'))
        if row.is_active:
            AepsProviderConfig.objects.filter(is_deleted=False, is_active=True).exclude(pk=row.pk or 0).update(
                is_active=False
            )
    secrets = decrypt_secret_payload(row.secrets_encrypted or '') or {}
    if data.get('password'):
        secrets['password'] = data['password']
    if 'password_mode' in data or 'password_format' in data:
        mode = str(data.get('password_mode') or data.get('password_format') or 'plain').strip().lower()
        secrets['password_mode'] = 'md5' if mode in ('md5', 'hashed', 'hash', 'digest') else 'plain'
    if data.get('secret_key'):
        secrets['secret_key'] = data['secret_key']
    if 'gstin_number' in data:
        secrets['gstin_number'] = (data.get('gstin_number') or '').strip()
    if 'company_or_shop_pan' in data:
        secrets['company_or_shop_pan'] = (data.get('company_or_shop_pan') or '').strip().upper()
    if data.get('use_bundled_certificate'):
        if not bundled_cert:
            return _err('Bundled Fingpay certificate not found on server', http_status=400)
        secrets['rsa_public_key_pem'] = bundled_cert
    elif data.get('rsa_public_key_pem') or data.get('public_key'):
        pem = (data.get('rsa_public_key_pem') or data.get('public_key') or '').strip()
        try:
            from apps.integrations.fingpay.crypto import _load_rsa_public_key

            _load_rsa_public_key(pem)
        except Exception as exc:
            return _err(str(exc), http_status=400)
        secrets['rsa_public_key_pem'] = pem
    # Ensure password_mode always present once secrets exist
    if secrets.get('password') and not secrets.get('password_mode'):
        secrets['password_mode'] = 'plain'
    row.secrets_encrypted = encrypt_secret_payload(secrets)
    row.updated_by = request.user
    row.save()
    if not AepsProviderConfig.objects.filter(is_deleted=False, is_active=True).exists():
        row.is_active = True
        row.save(update_fields=['is_active', 'updated_at'])
    out = _serialize_provider_row(row, bundled_cert=bundled_cert)
    return _ok(out, message=f'Provider config saved ({env})')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_provider_test(request):
    """Ping Fingpay with saved super-merchant credentials; return plain JSON for email to Tapits."""
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    try:
        from apps.integrations.fingpay.crypto import scrub_sensitive
        from apps.integrations.fingpay.registry import build_client_from_config, get_active_provider

        config = get_active_provider()
        client = build_client_from_config(config)
        egress = getattr(client, 'egress_ip', None) or DEFAULT_EGRESS_IP
        probe_merchant = {
            'merchantLoginId': 'CREDTEST01',
            'merchantLoginPin': '81dc9bdb52d04dc20036dbd8313ed055',
            'firstName': 'Test',
            'lastName': 'User',
            'middleName': '',
            'merchantPhoneNumber': '9999999999',
            'merchantAddress': {
                'merchantAddress1': 'Test Address One',
                'merchantAddress2': 'Test Address Two Line',
                'merchantState': 2,
                'merchantCityName': 'Hyderabad',
                'merchantDistrictName': 'Hyderabad',
                'merchantPinCode': '500001',
            },
            'companyLegalName': 'Credential Test',
            'userType': 'lakshmi',
            'companyType': 2,
            'emailId': 'credtest@example.com',
            'certificateOfIncorporationImage': 'True',
            'kyc': {
                'userPan': 'ABCDE1234F',
                'aadhaarNumber': '999999990019',
                'gstinNumber': '29AAACT9999A1Z5',
                'companyOrShopPan': 'ABCDE1234F',
                'merchantPanImage': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
                'maskedAadharImage': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
                'shopAndPanImage': 'True',
            },
            'settlementV1': {
                'companyBankAccountNumber': '1234567890',
                'bankIfscCode': 'SBIN0000001',
                'companyBankName': 'State Bank of India',
                'bankBranchName': 'Main',
                'bankAccountName': 'Test',
            },
            'tradeBusinessProof': 'True',
            'termsConditionCheck': 'True',
            'cancelledChequeImages': 'True',
            'physicalVerification': 'True',
            'videoKycWithLatLongData': 'True',
            'vedioKycWithLatLongData': 'True',
            'merchantKycAddressData': {
                'shopAddress': 'Shop Address',
                'shopCity': 'Hyderabad',
                'shopDistrict': 'Hyderabad',
                'shopState': 2,
                'shopPincode': '500001',
                'shopLatitude': 17.38,
                'shopLongitude': 78.48,
                'backgroundImageOfShop': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
            },
        }
        request_plain = {
            'username': client.super_merchant_login_id,
            'password': '<md5-of-integration-password>',
            'latitude': 17.38,
            'longitude': 78.48,
            'ipAddress': egress,
            'supermerchantId': int(client.super_merchant_id)
            if str(client.super_merchant_id).isdigit()
            else client.super_merchant_id,
            'merchant': probe_merchant,
        }
        force_simple = str(request.data.get('mode') or '').lower() == 'simple'
        use_simple = force_simple or client.api_mode == 'simple'
        endpoint = client.onboarding_create_url()
        resp = None
        transport_error = None
        mode = 'simple' if use_simple else client.onboarding_api_style
        try:
            if use_simple and client.api_mode != 'simple':
                resp = client.create_merchant_simple(
                    probe_merchant, latitude=17.38, longitude=78.48, ip_address=egress
                )
            else:
                resp = client.create_merchant(
                    probe_merchant, latitude=17.38, longitude=78.48, ip_address=egress
                )
        except Exception as exc:
            from apps.integrations.fingpay.client import FingpayClientError

            transport_error = str(exc)
            http_status = getattr(exc, 'status_code', None) if isinstance(exc, FingpayClientError) else None
            payload = getattr(exc, 'payload', None) if isinstance(exc, FingpayClientError) else None
            resp = {
                'status': False,
                'statusCode': str(http_status or ''),
                'message': transport_error,
                'provider_payload': scrub_sensitive(payload) if payload else None,
                'fingpay_exchange': getattr(exc, 'exchange', None) if isinstance(exc, FingpayClientError) else None,
                '_meta': {'http_status': http_status, 'mode': mode},
            }

        code = str((resp or {}).get('statusCode') or '')
        msg = str((resp or {}).get('message') or '')
        http_status = ((resp or {}).get('_meta') or {}).get('http_status')
        env_label = client.environment or ('simple' if use_simple else 'prod')
        ok_auth = (
            not transport_error
            and bool((resp or {}).get('status') is True or code in ('10000', '0', '00'))
            and code not in ('10005', '10004', '10015', '403', '401')
            and 'invalid super merchant' not in msg.lower()
            and 'modelcreation' not in msg.lower().replace(' ', '')
            and 'whitelisting' not in msg.lower()
            and http_status not in (401, 403)
        )
        hint = None
        if not ok_auth:
            if http_status == 403 or code == '403' or '403' in msg:
                hint = (
                    f'Host returned HTTP 403 from our server IP {egress} (AWS ELB). '
                    f'Ask Tapits to whitelist {egress} on this host.'
                )
            elif code == '10015' or 'whitelisting' in msg.lower():
                hint = (
                    f'Fingpay 10015 — IP whitelist pending for {egress}. '
                    'Ask Tapits to whitelist this IP for the active host/supermerchant.'
                )
            elif code == '10005' or 'invalid super merchant' in msg.lower():
                hint = (
                    'Invalid super merchant (10005). Use credentials that match the active profile '
                    '(UAT vs Production vs Simple). Do not reuse Production login on UAT.'
                )
            elif code == '10004' or 'modelcreation' in msg.lower().replace(' ', ''):
                hint = (
                    'Fingpay 10004 modelCreation — usually a bad request body (e.g. timestamp in JSON). '
                    'Retry after latest fix; if still failing, share response JSON with Tapits.'
                )
            else:
                hint = (
                    'Fingpay returned an application error. Check login/ID match the active environment.'
                )
        return _ok(
            {
                'mode': mode,
                'api_mode': client.api_mode,
                'endpoint': endpoint,
                'environment': env_label,
                'statusCode': code,
                'message': msg,
                'auth_accepted': ok_auth,
                'login': client.super_merchant_login_id,
                'super_merchant_id': client.super_merchant_id,
                'onboarding_base_url': client.onboarding_base_url,
                'ekyc_base_url': client.ekyc_base_url,
                'aeps_base_url': client.aeps_base_url,
                'server_ip': egress,
                'request_plain_json': scrub_sensitive(request_plain),
                'response_plain_json': scrub_sensitive(resp),
                'fingpay_exchange': (resp or {}).get('fingpay_exchange') or (resp or {}).get('_exchange'),
                'hint': hint,
            },
            message='Credential probe completed — copy request/response (or fingpay_exchange) to email Tapits',
        )
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_debug_logs(request):
    """List AEPS API audit logs; include full exchange when debug_mode captured them."""
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    from apps.aeps.models import AepsApiAuditLog

    qs = AepsApiAuditLog.objects.all().order_by('-created_at')
    endpoint = (request.query_params.get('endpoint') or '').strip()
    merchant_tran_id = (request.query_params.get('merchant_tran_id') or '').strip()
    debug_only = str(request.query_params.get('debug_only') or '').lower() in ('1', 'true', 'yes')
    if endpoint:
        qs = qs.filter(endpoint__icontains=endpoint)
    if merchant_tran_id:
        qs = qs.filter(merchant_tran_id__icontains=merchant_tran_id)
    if debug_only:
        qs = qs.filter(debug_enabled=True)
    try:
        limit = min(200, max(1, int(request.query_params.get('limit') or 50)))
    except (TypeError, ValueError):
        limit = 50
    rows = []
    for row in qs[:limit]:
        item = {
            'id': row.pk,
            'endpoint': row.endpoint,
            'method': row.method,
            'merchant_tran_id': row.merchant_tran_id,
            'http_status': row.http_status,
            'provider_status_code': row.provider_status_code,
            'latency_ms': row.latency_ms,
            'success': row.success,
            'error_message': row.error_message,
            'debug_enabled': row.debug_enabled,
            'request_summary': row.request_summary,
            'response_summary': row.response_summary,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
        if row.debug_enabled:
            item['request_headers'] = row.request_headers
            item['request_body'] = row.request_body
            item['response_body'] = row.response_body
            item['exchange_pack'] = row.exchange_pack
        rows.append(item)
    return _ok({'results': rows, 'count': len(rows)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_debug_log_detail(request, log_id: int):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    from apps.aeps.models import AepsApiAuditLog

    row = AepsApiAuditLog.objects.filter(pk=log_id).first()
    if not row:
        return _err('Log not found', http_status=404)
    return _ok(
        {
            'id': row.pk,
            'endpoint': row.endpoint,
            'method': row.method,
            'merchant_tran_id': row.merchant_tran_id,
            'http_status': row.http_status,
            'provider_status_code': row.provider_status_code,
            'latency_ms': row.latency_ms,
            'success': row.success,
            'error_message': row.error_message,
            'debug_enabled': row.debug_enabled,
            'request_summary': row.request_summary,
            'response_summary': row.response_summary,
            'request_headers': row.request_headers if row.debug_enabled else {},
            'request_body': row.request_body if row.debug_enabled else {},
            'response_body': row.response_body if row.debug_enabled else {},
            'exchange_pack': row.exchange_pack if row.debug_enabled else {},
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_entitlement_enable(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    from apps.authentication.models import User

    user_id = request.data.get('user_id')
    try:
        user = User.objects.get(pk=user_id)
        ent = entitlement_svc.enable_entitlement(actor=request.user, user=user, source='manual')
    except Exception as exc:
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
    return _ok({'user_id': user.pk, 'enabled': ent.enabled})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_entitlement_disable(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    from apps.authentication.models import User

    user_id = request.data.get('user_id')
    try:
        user = User.objects.get(pk=user_id)
        ent = entitlement_svc.disable_entitlement(
            actor=request.user, user=user, reason=request.data.get('reason') or ''
        )
    except Exception as exc:
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
    return _ok({'user_id': user.pk, 'enabled': ent.enabled})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_access_requests(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    status_f = request.query_params.get('status') or 'pending'
    qs = AepsAccessRequest.objects.filter(is_deleted=False).select_related('user')
    if status_f != 'all':
        qs = qs.filter(status=status_f)
    rows = [
        {
            'id': r.pk,
            'status': r.status,
            'reason': r.reason,
            'created_at': r.created_at.isoformat() if r.created_at else None,
            'user': {
                'id': r.user_id,
                'name': f'{r.user.first_name} {r.user.last_name}'.strip(),
                'phone': r.user.phone,
                'role': r.user.role,
            },
        }
        for r in qs[:200]
    ]
    return _ok({'results': rows})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_access_request_decide(request, request_id: int):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    try:
        row = entitlement_svc.decide_access_request(
            actor=request.user,
            request_id=request_id,
            decision=request.data.get('decision') or '',
            notes=request.data.get('notes') or '',
        )
    except Exception as exc:
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
    return _ok({'id': row.pk, 'status': row.status})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_merchants(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    qs = AepsMerchantProfile.objects.filter(is_deleted=False).select_related('user')
    stage = request.query_params.get('stage')
    if stage:
        qs = qs.filter(stage=stage)
    search = (request.query_params.get('search') or '').strip()
    if search:
        from django.db.models import Q

        qs = qs.filter(
            Q(merchant_login_id__icontains=search)
            | Q(user__phone__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
        )
    rows = [
        {
            'id': m.pk,
            'merchant_login_id': m.merchant_login_id,
            'stage': m.stage,
            'device_ready': m.device_ready,
            'device_imei': m.device_imei,
            'masked_aadhaar': m.masked_aadhaar or '',
            'last_error': (m.last_error or '')[:200],
            'updated_at': m.updated_at.isoformat() if m.updated_at else None,
            'user': {
                'id': m.user_id,
                'phone': m.user.phone,
                'role': m.user.role,
                'name': f'{m.user.first_name} {m.user.last_name}'.strip(),
            },
        }
        for m in qs[:300]
    ]
    return _ok({'results': rows})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_merchant_detail(request, merchant_id: int):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    merchant = (
        AepsMerchantProfile.objects.filter(pk=merchant_id, is_deleted=False)
        .select_related('user')
        .first()
    )
    if not merchant:
        return _err('Merchant not found', http_status=404)
    return _ok(onboarding_svc.admin_merchant_detail_payload(merchant))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_merchant_reset_pin(request, merchant_id: int):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    merchant = (
        AepsMerchantProfile.objects.filter(pk=merchant_id, is_deleted=False)
        .select_related('user')
        .first()
    )
    if not merchant:
        return _err('Merchant not found', http_status=404)
    new_pin = str(request.data.get('new_pin') or request.data.get('pin') or '').strip()
    try:
        result = onboarding_svc.reset_merchant_pin_via_onboarding(merchant=merchant, new_pin=new_pin)
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)
    merchant.refresh_from_db()
    return _ok(
        {
            **result,
            'merchant': onboarding_svc.admin_merchant_detail_payload(merchant),
        },
        message=result.get('message') or 'Merchant PIN reset submitted to Fingpay.',
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_entitlements_for_user(request, user_id: int):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    ent = AepsEntitlement.objects.filter(user_id=user_id, is_deleted=False).first()
    merchant = AepsMerchantProfile.objects.filter(user_id=user_id, is_deleted=False).first()
    return _ok(
        {
            'enabled': bool(ent and ent.enabled),
            'source': ent.source if ent else None,
            'merchant_stage': merchant.stage if merchant else None,
            'merchant_login_id': merchant.merchant_login_id if merchant else None,
        }
    )


# ----- onboarding / device / ekyc -----


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def onboarding_draft(request):
    try:
        if request.method == 'GET':
            data = onboarding_svc.get_onboarding_form(user=request.user)
            return _ok(data)
        data = onboarding_svc.save_onboarding_draft(
            user=request.user, payload=request.data.get('payload') or request.data
        )
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)
    return _ok(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def onboarding_image(request, field: str):
    """Fetch one stored KYC image as base64 (for Preview / Download JPG in the setup UI)."""
    try:
        data = onboarding_svc.get_onboarding_image(user=request.user, field=field)
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_submit(request):
    lat, lng = _geo(request)
    if lat is None or lng is None:
        return _err('latitude and longitude are required', code='GEO_REQUIRED')
    try:
        data = onboarding_svc.submit_onboarding(
            user=request.user,
            latitude=lat,
            longitude=lng,
            ip_address=get_client_ip(request) or '0.0.0.0',
            merchant_body=request.data.get('merchant') or request.data.get('payload'),
        )
    except Exception as exc:
        exchange = _exc_exchange(exc)
        # Always return data wrapper so frontend can render Copy pack even when exchange is {}.
        return _err(
            _flatten_exc_message(exc),
            code='PROVIDER_REJECTED',
            http_status=400,
            data={'fingpay_exchange': exchange} if exchange is not None else {'fingpay_exchange': None},
        )
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def device_register(request):
    try:
        data = onboarding_svc.register_device(
            user=request.user,
            device_imei=request.data.get('device_imei') or '',
            scanner_serial=request.data.get('scanner_serial') or '',
        )
    except Exception as exc:
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ekyc_start(request):
    lat, lng = _geo(request)
    if lat is None or lng is None:
        return _err('latitude and longitude are required', code='GEO_REQUIRED')
    try:
        data = onboarding_svc.ekyc_start(
            user=request.user,
            payload=request.data,
            device_imei=request.data.get('device_imei') or '',
            latitude=lat,
            longitude=lng,
        )
    except Exception as exc:
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ekyc_otp(request):
    try:
        data = onboarding_svc.ekyc_verify_otp(user=request.user, otp=str(request.data.get('otp') or ''))
    except Exception as exc:
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ekyc_resend(request):
    try:
        data = onboarding_svc.ekyc_resend_otp(user=request.user)
    except Exception as exc:
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ekyc_status(request):
    try:
        data = onboarding_svc.ekyc_status_check(
            user=request.user,
            kyc_type=str(request.data.get('kycType') or request.data.get('kyc_type') or 'EKYC'),
        )
    except Exception as exc:
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ekyc_biometric(request):
    lat, lng = _geo(request)
    if lat is None or lng is None:
        return _err('latitude and longitude are required', code='GEO_REQUIRED')
    capture = request.data.get('captureResponse') or request.data.get('capture_response')
    if not capture:
        return _err('captureResponse is required', code='DEVICE_REQUIRED')
    try:
        data = onboarding_svc.ekyc_biometric(
            user=request.user,
            capture_response=capture,
            latitude=lat,
            longitude=lng,
            aadhaar_number=request.data.get('aadhaarNumber')
            or request.data.get('aadharNumber')
            or '',
        )
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)
    return _ok(data)


# ----- products -----


def _product_view(request, runner):
    lat, lng = _geo(request)
    if lat is None or lng is None:
        return _err('latitude and longitude are required', code='GEO_REQUIRED')
    capture = request.data.get('captureResponse') or request.data.get('capture_response')
    if not capture:
        return _err('captureResponse is required', code='DEVICE_REQUIRED')
    try:
        data = runner(
            user=request.user,
            payload=request.data,
            capture_response=capture,
            latitude=lat,
            longitude=lng,
            ip=get_client_ip(request) or '',
        )
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def twofa_complete(request):
    lat, lng = _geo(request)
    capture = request.data.get('captureResponse') or request.data.get('capture_response')
    if lat is None or lng is None or not capture:
        return _err('latitude, longitude and captureResponse are required')
    try:
        data = products_svc.complete_daily_2fa(
            user=request.user,
            capture_response=capture,
            latitude=lat,
            longitude=lng,
            payload=request.data,
        )
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def txn_cw(request):
    return _product_view(request, products_svc.cash_withdrawal)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def txn_be(request):
    return _product_view(request, products_svc.balance_enquiry)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def txn_ms(request):
    return _product_view(request, products_svc.mini_statement)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def txn_ap(request):
    return _product_view(request, products_svc.aadhaar_pay)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def txn_cd(request):
    return _product_view(request, products_svc.cash_deposit)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def txn_cd_otp_generate(request):
    lat, lng = _geo(request)
    if lat is None or lng is None:
        return _err('latitude and longitude are required', code='GEO_REQUIRED')
    try:
        data = products_svc.cash_deposit_otp_generate(
            user=request.user,
            payload=request.data,
            latitude=lat,
            longitude=lng,
            ip=get_client_ip(request) or '',
        )
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def txn_cd_otp_validate(request):
    try:
        data = products_svc.cash_deposit_otp_validate(
            user=request.user,
            merchant_tran_id=str(request.data.get('merchant_tran_id') or request.data.get('merchantTranId') or ''),
            otp=str(request.data.get('otp') or ''),
        )
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def txn_cd_otp_submit(request):
    lat, lng = _geo(request)
    if lat is None or lng is None:
        return _err('latitude and longitude are required', code='GEO_REQUIRED')
    try:
        data = products_svc.cash_deposit_otp_submit(
            user=request.user,
            merchant_tran_id=str(request.data.get('merchant_tran_id') or request.data.get('merchantTranId') or ''),
            latitude=lat,
            longitude=lng,
        )
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def txn_status_check(request, merchant_tran_id: str):
    try:
        data = products_svc.status_check(
            user=request.user,
            merchant_tran_id=merchant_tran_id,
            otp_mode=bool(request.data.get('otp_mode') or request.data.get('otpMode')),
        )
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def txn_acknowledge(request, merchant_tran_id: str):
    from apps.aeps.models import AepsTransaction

    try:
        txn = AepsTransaction.objects.get(
            user=request.user, merchant_tran_id=merchant_tran_id, is_deleted=False
        )
    except AepsTransaction.DoesNotExist:
        return _err('Transaction not found', http_status=404)
    try:
        products_svc.acknowledge_transaction(
            txn, otp_mode=bool(request.data.get('otp_mode') or request.data.get('otpMode'))
        )
    except Exception as exc:
        return _err(str(exc), http_status=400)
    return _ok({'transaction': products_svc.serialize_txn(txn)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def banks_list(request):
    list_type = request.query_params.get('type') or 'aeps'
    force = str(request.query_params.get('refresh') or '').lower() in ('1', 'true', 'yes')
    if force:
        try:
            products_svc.sync_bank_iin_cache()
        except Exception as exc:
            return _err(_flatten_exc_message(exc), http_status=400)
    rows = products_svc.list_banks(list_type, auto_sync=not force)
    return _ok({'results': rows, 'count': len(rows)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def banks_sync(request):
    # Entitled merchants/admins can refresh the bank cache — needed for 2FA / trade.
    from apps.aeps.services.gates import is_entitled

    if not (_require_admin(request) or is_entitled(request.user)):
        return _err('AEPS access required', http_status=403)
    try:
        n = products_svc.sync_bank_iin_cache()
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)
    return _ok({'synced': n})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transactions_list(request):
    admin_all = _require_admin(request) and request.query_params.get('scope') == 'all'
    data = reports_svc.query_transactions(
        user=request.user,
        admin_all=admin_all,
        product=request.query_params.get('product'),
        status=request.query_params.get('status'),
        date_from=request.query_params.get('date_from'),
        date_to=request.query_params.get('date_to'),
        search=request.query_params.get('search'),
        limit=min(int(request.query_params.get('limit') or 50), 200),
        offset=int(request.query_params.get('offset') or 0),
    )
    return _ok(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reports_summary(request):
    admin_all = _require_admin(request) and request.query_params.get('scope') == 'all'
    data = reports_svc.summary_stats(
        user=request.user,
        admin_all=admin_all,
        days=int(request.query_params.get('days') or 7),
    )
    return _ok(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_recon_batches(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    rows = [
        {
            'id': b.pk,
            'txn_date': b.txn_date,
            'item_count': b.item_count,
            'created_at': b.created_at.isoformat() if b.created_at else None,
        }
        for b in AepsReconBatch.objects.all()[:100]
    ]
    return _ok({'results': rows})


# ----- webhooks (no auth — hash verified) -----


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def webhook_three_way_recon(request):
    raw = request.body.decode('utf-8') if request.body else ''
    headers = {k: v for k, v in request.headers.items()}
    # Also accept query/header variants
    if request.META.get('HTTP_HASH'):
        headers['hash'] = request.META['HTTP_HASH']
    if request.META.get('HTTP_TXNDATE'):
        headers['txnDate'] = request.META['HTTP_TXNDATE']
    result = recon_svc.handle_three_way_recon(
        raw_body=raw,
        headers=headers,
        client_ip=get_client_ip(request),
    )
    return Response(result, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def webhook_callback(request):
    payload = request.data if isinstance(request.data, dict) else {}
    if not payload and request.body:
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            payload = {}
    result = recon_svc.handle_transaction_callback(payload=payload)
    return Response(result, status=status.HTTP_200_OK)
