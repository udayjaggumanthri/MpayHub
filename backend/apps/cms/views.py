"""Uber CMS HTTP API — entitlement, launch, wallet, reports, inbound webhooks."""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.cms.models import (
    CmsAgentProfile,
    CmsApiAuditLog,
    CmsEntitlement,
    CmsProviderConfig,
)
from apps.cms.services import entitlement as entitlement_svc
from apps.cms.services import inbound as inbound_svc
from apps.cms.services import launch as launch_svc
from apps.cms.services import reports as reports_svc
from apps.cms.services import wallet as wallet_svc
from apps.cms.services.gates import me_status_payload
from apps.cms.services.registry import get_active_cms_config, invalidate_cms_config_cache
from apps.core.roles import is_platform_operator
from apps.core.utils import decrypt_secret_payload, encrypt_secret_payload
from apps.session_security.services.ip import get_client_ip


def _ok(data=None, message='', http_status=200):
    return Response({'success': True, 'message': message, 'data': data or {}}, status=http_status)


def _err(message, *, code=None, http_status=400, errors=None, data=None):
    body = {'success': False, 'message': str(message)}
    if code:
        body['code'] = code
    if errors:
        body['errors'] = errors
    if data is not None:
        body['data'] = data
    return Response(body, status=http_status)


def _flatten_exc_message(exc) -> str:
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


def _require_admin(request):
    return is_platform_operator(request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_status(request):
    return _ok(me_status_payload(request.user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def launch(request):
    try:
        data = launch_svc.prepare_launch(
            user=request.user,
            amount=request.data.get('amount'),
            latitude=request.data.get('latitude'),
            longitude=request.data.get('longitude'),
            client_ip=get_client_ip(request),
            additional_params=request.data.get('additionalParams'),
        )
        return _ok(data, message='CMS launch URL ready')
    except Exception as exc:
        from rest_framework.exceptions import PermissionDenied, ValidationError

        if isinstance(exc, PermissionDenied):
            return _err(_flatten_exc_message(exc), code='CMS_FORBIDDEN', http_status=403)
        if isinstance(exc, ValidationError):
            return _err(_flatten_exc_message(exc), http_status=400)
        return _err(str(exc), http_status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_get(request):
    if not entitlement_svc.is_entitled(request.user) and not _require_admin(request):
        return _err('CMS not enabled', code='CMS_NOT_ENTITLED', http_status=403)
    snap = wallet_svc.wallet_snapshot(request.user)
    entries = reports_svc.list_wallet_entries(user=request.user, limit=50)
    return _ok({**snap, 'entries': entries})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wallet_fund(request):
    if not entitlement_svc.is_entitled(request.user):
        return _err('CMS not enabled', code='CMS_NOT_ENTITLED', http_status=403)
    try:
        from apps.core.financial_access import assert_can_perform_financial_txn
        from apps.core.maintenance_mode import MODULE_CMS, assert_module_available

        assert_module_available(MODULE_CMS)
        assert_can_perform_financial_txn(request.user)
        amount = Decimal(str(request.data.get('amount') or '0'))
        data = wallet_svc.fund_from_main(user=request.user, amount=amount)
        return _ok(data, message='CMS wallet funded')
    except Exception as exc:
        from rest_framework.exceptions import PermissionDenied, ValidationError

        if isinstance(exc, PermissionDenied):
            return _err(_flatten_exc_message(exc), http_status=403)
        if isinstance(exc, ValidationError):
            return _err(_flatten_exc_message(exc), http_status=400)
        return _err(str(exc), http_status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transactions_list(request):
    admin_all = _require_admin(request) and request.query_params.get('scope') == 'all'
    data = reports_svc.query_transactions(
        user=request.user,
        admin_all=admin_all,
        status=request.query_params.get('status'),
        date_from=request.query_params.get('date_from'),
        date_to=request.query_params.get('date_to'),
        search=request.query_params.get('search'),
        limit=int(request.query_params.get('limit') or 50),
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
        days=int(request.query_params.get('days') or 30),
        date_from=request.query_params.get('date_from'),
        date_to=request.query_params.get('date_to'),
        status=request.query_params.get('status'),
    )
    return _ok(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reports_export_csv(request):
    admin_all = _require_admin(request) and request.query_params.get('scope') == 'all'
    return reports_svc.export_transactions_csv(
        user=request.user,
        admin_all=admin_all,
        status=request.query_params.get('status'),
        date_from=request.query_params.get('date_from'),
        date_to=request.query_params.get('date_to'),
        search=request.query_params.get('search'),
        limit=int(request.query_params.get('limit') or 5000),
    )


def _serialize_provider(row: CmsProviderConfig, *, include_secrets_meta: bool = True) -> dict:
    secrets = decrypt_secret_payload(row.secrets_encrypted or '') or {}
    out = {
        'id': row.pk,
        'name': row.name,
        'environment': row.environment,
        'is_active': row.is_active,
        'login_type': row.login_type,
        'super_merchant_id': row.super_merchant_id,
        'cms_base_url': row.cms_base_url,
        'login_path': row.login_path,
        'hash_template': row.hash_template,
        'allowed_inbound_ips': row.allowed_inbound_ips or [],
        'debug_mode': row.debug_mode,
        'hold_ttl_hours': row.hold_ttl_hours,
        'notes': row.notes,
        'has_super_merchant_skey': bool(secrets.get('super_merchant_skey') or secrets.get('superMerchantSkey')),
        'has_secret_key': bool(secrets.get('secret_key') or secrets.get('secretKey')),
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }
    if not include_secrets_meta:
        out.pop('has_super_merchant_skey', None)
        out.pop('has_secret_key', None)
    return out


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def admin_provider_config(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)

    if request.method == 'GET':
        row = CmsProviderConfig.objects.filter(is_deleted=False).order_by('-is_active', '-updated_at').first()
        if not row:
            return _ok({'config': None})
        return _ok({'config': _serialize_provider(row)})

    data = request.data if isinstance(request.data, dict) else {}
    name = str(data.get('name') or 'default')[:100]
    row, _ = CmsProviderConfig.objects.get_or_create(
        name=name,
        defaults={'environment': 'uat', 'is_active': False},
    )
    if data.get('environment') in ('uat', 'prod'):
        row.environment = data['environment']
    if 'is_active' in data:
        row.is_active = bool(data['is_active'])
        if row.is_active:
            CmsProviderConfig.objects.exclude(pk=row.pk).filter(is_active=True).update(is_active=False)
    if 'login_type' in data:
        row.login_type = str(data.get('login_type') or '2')[:8]
    if 'super_merchant_id' in data:
        row.super_merchant_id = str(data.get('super_merchant_id') or '')[:64]
    if 'cms_base_url' in data:
        row.cms_base_url = str(data.get('cms_base_url') or '')[:500]
    if 'login_path' in data:
        row.login_path = str(data.get('login_path') or '/UberCMSBC/#/login')[:200]
    if 'hash_template' in data:
        row.hash_template = str(data.get('hash_template') or '{payload}{secret_key}')[:64]
    if 'allowed_inbound_ips' in data:
        ips = data.get('allowed_inbound_ips') or []
        if isinstance(ips, str):
            ips = [x.strip() for x in ips.split(',') if x.strip()]
        row.allowed_inbound_ips = list(ips)
    if 'debug_mode' in data:
        row.debug_mode = bool(data['debug_mode'])
    if 'hold_ttl_hours' in data:
        try:
            row.hold_ttl_hours = max(1, int(data['hold_ttl_hours']))
        except (TypeError, ValueError):
            pass
    if 'notes' in data:
        row.notes = str(data.get('notes') or '')

    secrets = decrypt_secret_payload(row.secrets_encrypted or '') or {}
    if data.get('super_merchant_skey'):
        secrets['super_merchant_skey'] = str(data['super_merchant_skey']).strip()
    if data.get('secret_key'):
        secrets['secret_key'] = str(data['secret_key']).strip()
    if secrets:
        row.secrets_encrypted = encrypt_secret_payload(secrets)

    row.updated_by = request.user
    row.save()
    invalidate_cms_config_cache()
    return _ok({'config': _serialize_provider(row)}, message='CMS provider saved')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_entitlement_enable(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    from apps.authentication.models import User

    user_id = request.data.get('user_id')
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return _err('User not found', http_status=404)
    try:
        ent = entitlement_svc.enable_entitlement(actor=request.user, user=user)
        return _ok({'user_id': user.pk, 'enabled': ent.enabled})
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_entitlement_disable(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    from apps.authentication.models import User

    user_id = request.data.get('user_id')
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return _err('User not found', http_status=404)
    try:
        ent = entitlement_svc.disable_entitlement(
            actor=request.user,
            user=user,
            reason=str(request.data.get('reason') or ''),
        )
        return _ok({'user_id': user.pk, 'enabled': ent.enabled})
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_agents(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    rows = []
    # Only agents with CMS currently enabled (profile entitlement).
    ents = (
        CmsEntitlement.objects.filter(enabled=True, is_deleted=False)
        .select_related('user')
        .order_by('-updated_at')[:200]
    )
    for ent in ents:
        a = CmsAgentProfile.objects.filter(user=ent.user, is_deleted=False).first()
        if not a:
            continue
        snap = wallet_svc.wallet_snapshot(a.user)
        rows.append(
            {
                'id': a.pk,
                'user_id': a.user_id,
                'user_name': getattr(a.user, 'full_name', None) or a.user.phone,
                'bc_login_id': a.bc_login_id,
                'status': a.status,
                'mobile_number': a.mobile_number,
                'entitled': True,
                'wallet': snap,
                'activated_at': a.activated_at.isoformat() if a.activated_at else None,
            }
        )
    return _ok({'results': rows})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_entitlements_for_user(request, user_id: int):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    ent = CmsEntitlement.objects.filter(user_id=user_id, is_deleted=False).first()
    agent = CmsAgentProfile.objects.filter(user_id=user_id, is_deleted=False).first()
    return _ok(
        {
            'enabled': bool(ent and ent.enabled),
            'source': ent.source if ent else None,
            'agent_status': agent.status if agent else None,
            'bc_login_id': agent.bc_login_id if agent else None,
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_agent_reset_pin(request, agent_id: int):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    try:
        data = entitlement_svc.reset_agent_pin(actor=request.user, agent_id=agent_id)
        return _ok(data, message='PIN reset')
    except CmsAgentProfile.DoesNotExist:
        return _err('Agent not found', http_status=404)
    except Exception as exc:
        return _err(_flatten_exc_message(exc), http_status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_audit_logs(request):
    if not _require_admin(request):
        return _err('Admin only', http_status=403)
    qs = CmsApiAuditLog.objects.all().order_by('-created_at')[:100]
    rows = [
        {
            'id': r.pk,
            'endpoint': r.endpoint,
            'success': r.success,
            'fp_transaction_id': r.fp_transaction_id,
            'merchant_transaction_id': r.merchant_transaction_id,
            'error_message': r.error_message,
            'client_ip': r.client_ip,
            'latency_ms': r.latency_ms,
            'created_at': r.created_at.isoformat() if r.created_at else None,
            'request_summary': r.request_summary,
            'response_summary': r.response_summary,
            'debug_enabled': r.debug_enabled,
            'request_body': r.request_body if r.debug_enabled else None,
            'response_body': r.response_body if r.debug_enabled else None,
        }
        for r in qs
    ]
    return _ok({'results': rows, 'count': len(rows)})


# ----- inbound webhooks (hash verified) -----


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def webhook_wallet_check(request):
    raw = request.body.decode('utf-8') if request.body else ''
    headers = {k: v for k, v in request.headers.items()}
    if request.META.get('HTTP_HASH'):
        headers['hash'] = request.META['HTTP_HASH']
    result = inbound_svc.handle_wallet_check(
        raw_body=raw,
        headers=headers,
        client_ip=get_client_ip(request),
    )
    return Response(result, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def webhook_wallet_debit(request):
    raw = request.body.decode('utf-8') if request.body else ''
    headers = {k: v for k, v in request.headers.items()}
    if request.META.get('HTTP_HASH'):
        headers['hash'] = request.META['HTTP_HASH']
    result = inbound_svc.handle_wallet_debit(
        raw_body=raw,
        headers=headers,
        client_ip=get_client_ip(request),
    )
    return Response(result, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def webhook_txn_result(request):
    payload = request.data if isinstance(request.data, dict) else {}
    if not payload and request.body:
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            payload = {}
    result = inbound_svc.handle_txn_result(payload=payload, client_ip=get_client_ip(request))
    return Response(result, status=status.HTTP_200_OK)
