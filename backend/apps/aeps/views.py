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


def _err(message, *, code=None, http_status=400, errors=None):
    body = {'success': False, 'message': str(message)}
    if code:
        body['code'] = code
    if errors:
        body['errors'] = errors
    return Response(body, status=http_status)


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


SERVER_EGRESS_IP = '57.131.39.21'

ENV_PRESETS = {
    'uat': {
        'name': 'fingpay-uat',
        'environment': 'uat',
        'onboarding_base_url': 'https://fpuat.tapits.in/fpaepsweb',
        'ekyc_base_url': 'https://fpekyc.tapits.in',
        'aeps_base_url': 'https://fpuat.tapits.in',
        'recon_base_url': '',
        'bank_list_url': 'https://fpuat.tapits.in/fpaepsservice/api/bankdata/bank/details',
        'aadhaar_pay_bank_list_url': 'https://fpuat.tapits.in/fpaepsservice/api/bankdata/bank/aadharpay',
    },
    'prod': {
        'name': 'fingpay-prod',
        'environment': 'prod',
        'onboarding_base_url': 'https://fingpayap.tapits.in/fpaepsweb',
        'ekyc_base_url': 'https://fpekyc.tapits.in',
        'aeps_base_url': 'https://fingpayap.tapits.in',
        'recon_base_url': '',
        'bank_list_url': 'https://fingpayap.tapits.in/fpaepsservice/api/bankdata/bank/details',
        'aadhaar_pay_bank_list_url': 'https://fingpayap.tapits.in/fpaepsservice/api/bankdata/bank/aadharpay',
    },
}


def _serialize_provider_row(row, *, bundled_cert: str = '') -> dict:
    secrets = decrypt_secret_payload(row.secrets_encrypted or '') or {} if row else {}
    return {
        'id': row.pk if row else None,
        'configured': bool(row),
        'name': row.name if row else '',
        'environment': row.environment if row else 'prod',
        'is_active': bool(row and row.is_active),
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
        'server_egress_ip': SERVER_EGRESS_IP,
        'whitelist_note': (
            f'Share ONLY this server IP with Tapits for whitelist: {SERVER_EGRESS_IP}. '
            'Do not use old AWS EC2 IPs from other portals (e.g. 52.66.x / 13.234.x / 3.108.x).'
        ),
        'bundled_public_certificate': bundled_cert,
        'has_bundled_certificate': bool(bundled_cert),
    }


def _get_or_create_env_row(environment: str) -> AepsProviderConfig:
    env = 'uat' if environment == 'uat' else 'prod'
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
            .exclude(environment='uat')
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
        onboarding_base_url=preset['onboarding_base_url'],
        ekyc_base_url=preset['ekyc_base_url'],
        aeps_base_url=preset['aeps_base_url'],
        recon_base_url=preset['recon_base_url'],
        bank_list_url=preset['bank_list_url'],
        aadhaar_pay_bank_list_url=preset['aadhaar_pay_bank_list_url'],
        is_active=False,
    )


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def admin_provider_config(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    from apps.integrations.fingpay.crypto import load_bundled_fingpay_certificate

    bundled_cert = load_bundled_fingpay_certificate()
    env = (request.query_params.get('environment') or request.data.get('environment') or '').strip().lower()
    if env not in ('uat', 'prod'):
        active = AepsProviderConfig.objects.filter(is_active=True, is_deleted=False).order_by('-updated_at').first()
        env = active.environment if active and active.environment in ('uat', 'prod') else 'prod'

    if request.method == 'GET':
        row = (
            AepsProviderConfig.objects.filter(environment=env, is_deleted=False)
            .order_by('-is_active', '-updated_at')
            .first()
        )
        if not row and env == 'prod':
            row = AepsProviderConfig.objects.filter(is_deleted=False).order_by('-is_active', '-updated_at').first()
        envs = []
        for e in ('uat', 'prod'):
            r = AepsProviderConfig.objects.filter(environment=e, is_deleted=False).order_by('-is_active', '-updated_at').first()
            envs.append(
                {
                    'environment': e,
                    'configured': bool(r and (r.super_merchant_login_id or r.secrets_encrypted)),
                    'is_active': bool(r and r.is_active),
                    'super_merchant_id': r.super_merchant_id if r else '',
                    'super_merchant_login_id': r.super_merchant_login_id if r else '',
                }
            )
        payload = _serialize_provider_row(row, bundled_cert=bundled_cert)
        payload['environments'] = envs
        payload['presets'] = ENV_PRESETS
        payload['credential_help'] = {
            'public_certificate': (
                'Use fingpay_public_production.cer from AEPS docs '
                '(-----BEGIN CERTIFICATE-----). Same file is bundled for one-click load.'
            ),
            'secret_key': (
                'Issued by Fingpay Integration Team by email — required for 3-way recon hash only.'
            ),
            'encryption': 'PHP /php/ APIs use AES-128-CBC + RSA eskey (certificate).',
        }
        return _ok(payload)

    data = request.data or {}
    env = 'uat' if str(data.get('environment') or env).lower() == 'uat' else 'prod'
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
    ):
        if field in data:
            setattr(row, field, data.get(field) or '')
    row.name = preset['name']
    row.environment = env
    # Fill missing URLs from preset for that environment
    for url_field in (
        'onboarding_base_url',
        'ekyc_base_url',
        'aeps_base_url',
        'bank_list_url',
        'aadhaar_pay_bank_list_url',
    ):
        if not getattr(row, url_field):
            setattr(row, url_field, preset.get(url_field) or '')
    if 'request_timeout_seconds' in data:
        row.request_timeout_seconds = int(data.get('request_timeout_seconds') or 180)
    activate = bool(data.get('is_active')) if 'is_active' in data else bool(data.get('activate'))
    if activate or data.get('make_active'):
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
    row.secrets_encrypted = encrypt_secret_payload(secrets)
    row.updated_by = request.user
    row.save()
    # Ensure at least one active
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
        # Minimal merchant body — we only care whether SM auth is accepted.
        probe_merchant = {
            'merchantLoginId': 'CREDTEST01',
            'merchantLoginPin': '1234',  # doc: plain PIN
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
            'ipAddress': '57.131.39.21',
            'supermerchantId': int(client.super_merchant_id)
            if str(client.super_merchant_id).isdigit()
            else client.super_merchant_id,
            'merchant': probe_merchant,
        }
        # Prefer PHP encrypted path (doc). Optional ?mode=simple for UAT plain JSON only.
        force_simple = str(request.data.get('mode') or '').lower() == 'simple'
        use_simple = force_simple and 'fpuat' in (client.onboarding_base_url or '').lower()
        endpoint = (
            f'{client.onboarding_base_url}/api/onboarding/merchant/simple/creation/v2'
            if use_simple
            else f'{client.onboarding_base_url}/api/onboarding/merchant/php/creation/v2'
        )
        resp = None
        transport_error = None
        try:
            if use_simple:
                resp = client.create_merchant_simple(
                    probe_merchant, latitude=17.38, longitude=78.48, ip_address='57.131.39.21'
                )
                mode = 'simple'
            else:
                resp = client.create_merchant(
                    probe_merchant, latitude=17.38, longitude=78.48, ip_address='57.131.39.21'
                )
                mode = 'php'
        except Exception as exc:
            from apps.integrations.fingpay.client import FingpayClientError

            mode = 'simple' if use_simple else 'php'
            transport_error = str(exc)
            http_status = getattr(exc, 'status_code', None) if isinstance(exc, FingpayClientError) else None
            payload = getattr(exc, 'payload', None) if isinstance(exc, FingpayClientError) else None
            resp = {
                'status': False,
                'statusCode': str(http_status or ''),
                'message': transport_error,
                'provider_payload': scrub_sensitive(payload) if payload else None,
                '_meta': {'http_status': http_status, 'mode': mode},
            }

        code = str((resp or {}).get('statusCode') or '')
        msg = str((resp or {}).get('message') or '')
        http_status = ((resp or {}).get('_meta') or {}).get('http_status')
        is_uat = 'fpuat' in (client.onboarding_base_url or '').lower()
        # Auth OK only if Fingpay accepted SM and did not return known reject/model errors.
        # Note: a full merchant create may still fail validation later; probe cares about SM auth.
        ok_auth = (
            not transport_error
            and bool((resp or {}).get('status') is True or code in ('10000', '0', '00'))
            and code not in ('10005', '10004', '403', '401')
            and 'invalid super merchant' not in msg.lower()
            and 'modelcreation' not in msg.lower().replace(' ', '')
            and http_status not in (401, 403)
        )
        # Soft-pass: reached app and got a structured validation error that is NOT bad SM/auth
        reached_app = not transport_error and http_status not in (401, 403) and code not in ('403', '401', '')
        if not ok_auth and reached_app and code == '10005':
            ok_auth = False
        hint = None
        if not ok_auth:
            if http_status == 403 or code == '403' or '403' in msg:
                hint = (
                    'Host returned HTTP 403 from our server IP 57.131.39.21 (AWS ELB). '
                    'Ask Tapits to whitelist 57.131.39.21 on this host — not old AWS IPs.'
                )
            elif code == '10005' or 'invalid super merchant' in msg.lower():
                if is_uat:
                    hint = (
                        'UAT rejected these credentials (10005 Invalid super merchant). '
                        'Production login Mpayhubd / 1501 is not valid on fpuat. '
                        'Ask Tapits for separate UAT SuperMerchant login/ID/password, '
                        'save them under the UAT tab, then retest. '
                        'For go-live keep Production active once fingpayap whitelist works.'
                    )
                else:
                    hint = (
                        'Production rejected Integration credentials (10005). Confirm with Tapits: '
                        'Mpayhubd / 1234d / ID 1501 on fingpayap.tapits.in, IP 57.131.39.21 whitelisted. '
                        'Do not use Aggregator portal password mpayhub1234 for API.'
                    )
            elif code == '10004' or 'modelcreation' in msg.lower().replace(' ', ''):
                hint = (
                    'Fingpay 10004 modelCreation — usually a bad request body (e.g. timestamp in JSON). '
                    'Retry after latest fix; if still failing, share response JSON with Tapits.'
                )
            else:
                hint = (
                    'Fingpay returned an application error. Check login/ID match the active environment '
                    '(UAT vs Production use different SuperMerchant credentials).'
                )
        return _ok(
            {
                'mode': mode,
                'endpoint': endpoint,
                'environment': 'uat' if is_uat else 'prod',
                'statusCode': code,
                'message': msg,
                'auth_accepted': ok_auth,
                'login': client.super_merchant_login_id,
                'super_merchant_id': client.super_merchant_id,
                'onboarding_base_url': client.onboarding_base_url,
                'ekyc_base_url': client.ekyc_base_url,
                'aeps_base_url': client.aeps_base_url,
                'server_ip': '57.131.39.21',
                'request_plain_json': scrub_sensitive(request_plain),
                'response_plain_json': scrub_sensitive(resp),
                'hint': hint,
            },
            message='Credential probe completed — copy request_plain_json + response_plain_json to email Tapits',
        )
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)


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
        return _err(_flatten_exc_message(exc), http_status=400)
    return _ok(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def device_register(request):
    try:
        data = onboarding_svc.register_device(user=request.user, device_imei=request.data.get('device_imei') or '')
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
        )
    except Exception as exc:
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
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
        detail = getattr(exc, 'detail', None)
        if isinstance(detail, dict):
            return _err(detail.get('message') or str(detail), code=detail.get('code'), http_status=400)
        return _err(str(detail or exc), http_status=400)
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
        detail = getattr(exc, 'detail', None)
        if isinstance(detail, dict):
            return _err(detail.get('message') or str(detail), code=detail.get('code'), http_status=400)
        return _err(str(detail or exc), http_status=400)
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
        detail = getattr(exc, 'detail', None)
        if isinstance(detail, dict):
            return _err(detail.get('message') or str(detail), code=detail.get('code'), http_status=400)
        return _err(str(detail or exc), http_status=400)
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
        detail = getattr(exc, 'detail', None)
        if isinstance(detail, dict):
            return _err(detail.get('message') or str(detail), code=detail.get('code'), http_status=400)
        return _err(str(detail or exc), http_status=400)
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
        detail = getattr(exc, 'detail', None)
        if isinstance(detail, dict):
            return _err(detail.get('message') or str(detail), code=detail.get('code'), http_status=400)
        return _err(str(detail or exc), http_status=400)
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
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
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
    return _ok({'results': products_svc.list_banks(list_type)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def banks_sync(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    try:
        n = products_svc.sync_bank_iin_cache()
    except Exception as exc:
        return _err(str(exc), http_status=400)
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
