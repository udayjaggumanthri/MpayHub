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
    if isinstance(detail, dict):
        if detail.get('message') is not None:
            return str(detail.get('message'))
        # {'field': [ErrorDetail...]} or {'field': 'msg'}
        parts = []
        for key, val in detail.items():
            if key in ('code',):
                continue
            if isinstance(val, (list, tuple)):
                parts.append(f'{key}: {", ".join(str(x) for x in val)}')
            else:
                parts.append(f'{key}: {val}' if key != 'message' else str(val))
        return '; '.join(parts) if parts else str(detail)
    if isinstance(detail, (list, tuple)):
        return '; '.join(str(x) for x in detail)
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


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def admin_provider_config(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    row = AepsProviderConfig.objects.filter(is_deleted=False).order_by('-is_active', '-updated_at').first()
    if request.method == 'GET':
        if not row:
            return _ok({'configured': False})
        secrets = decrypt_secret_payload(row.secrets_encrypted or '') or {}
        return _ok(
            {
                'configured': True,
                'id': row.pk,
                'name': row.name,
                'environment': row.environment,
                'is_active': row.is_active,
                'super_merchant_id': row.super_merchant_id,
                'super_merchant_login_id': row.super_merchant_login_id,
                'onboarding_base_url': row.onboarding_base_url,
                'ekyc_base_url': row.ekyc_base_url,
                'aeps_base_url': row.aeps_base_url,
                'recon_base_url': row.recon_base_url,
                'bank_list_url': row.bank_list_url,
                'aadhaar_pay_bank_list_url': row.aadhaar_pay_bank_list_url,
                'request_timeout_seconds': row.request_timeout_seconds,
                'notes': row.notes,
                'has_password': bool(secrets.get('password')),
                'has_secret_key': bool(secrets.get('secret_key')),
                'has_public_key': bool(secrets.get('rsa_public_key_pem') or secrets.get('public_key')),
            }
        )

    data = request.data or {}
    if not row:
        row = AepsProviderConfig(name='default')
    for field in (
        'name',
        'environment',
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
    if 'request_timeout_seconds' in data:
        row.request_timeout_seconds = int(data.get('request_timeout_seconds') or 180)
    if 'is_active' in data:
        row.is_active = bool(data.get('is_active'))
    secrets = decrypt_secret_payload(row.secrets_encrypted or '') or {}
    if data.get('password'):
        secrets['password'] = data['password']
    if data.get('secret_key'):
        secrets['secret_key'] = data['secret_key']
    if data.get('rsa_public_key_pem') or data.get('public_key'):
        secrets['rsa_public_key_pem'] = data.get('rsa_public_key_pem') or data.get('public_key')
    row.secrets_encrypted = encrypt_secret_payload(secrets)
    row.updated_by = request.user
    row.save()
    return _ok({'id': row.pk}, message='Provider config saved')


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_draft(request):
    try:
        data = onboarding_svc.save_onboarding_draft(user=request.user, payload=request.data.get('payload') or request.data)
    except Exception as exc:
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
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
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
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
            user=request.user, capture_response=capture, latitude=lat, longitude=lng
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
def txn_status_check(request, merchant_tran_id: str):
    try:
        data = products_svc.status_check(user=request.user, merchant_tran_id=merchant_tran_id)
    except Exception as exc:
        return _err(str(getattr(exc, 'detail', None) or exc), http_status=400)
    return _ok(data)


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
