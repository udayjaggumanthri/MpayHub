"""
BBPS views for the mPayhub platform.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
from django.db import IntegrityError

from apps.bbps.models import (
    BbpsApiAuditLog,
    BbpsBillerMaster,
    BillPayment,
    BbpsCategoryCommissionRule,
    BbpsComplaint,
    BbpsCommissionAudit,
    BbpsPaymentAttempt,
    BbpsProviderBillerMap,
    BbpsPushWebhookEvent,
    BbpsServiceCategory,
    BbpsServiceProvider,
)
from apps.bbps.serializers import (
    BillPaymentSerializer,
    FetchBillSerializer,
    BillPaymentCreateSerializer,
    BillAvenueAgentProfileSerializer,
    BillAvenueConfigSerializer,
    BillAvenueModeChannelPolicySerializer,
    BillAvenueSecretUpdateSerializer,
    BbpsCategoryCommissionRuleSerializer,
    BbpsBillerMasterLiteSerializer,
    BbpsProviderBillerMapSerializer,
    BbpsServiceCategorySerializer,
    BbpsServiceProviderSerializer,
    BillerSyncRequestSerializer,
    ComplaintRegisterSerializer,
    ComplaintTrackSerializer,
    DepositEnquirySerializer,
    PlanPullSerializer,
    StatusPollSerializer,
    TransactionQuerySerializer,
)
from apps.bbps.services import (
    governance_block_reasons_for_map,
    governance_readiness_for_biller,
    get_bill_categories,
    get_biller_input_schema,
    get_billers_by_category,
    get_providers_by_category,
    get_setup_readiness,
    normalize_category_code,
)
from apps.bbps.service_flow import (
    enquire_deposits,
    fetch_bill_with_cache,
    poll_attempt_status,
    process_bill_payment_flow,
    pull_biller_plans,
    register_complaint,
    sync_biller_info,
    track_complaint,
    validate_biller_inputs,
)
from apps.bbps.service_flow.commission_service import resolve_commission_for_payment
from apps.core.exceptions import InsufficientBalance, TransactionFailed
from apps.core.financial_access import assert_can_perform_financial_txn
from apps.core.permissions import IsAdmin
from apps.integrations.billavenue.crypto import decrypt_payload
from apps.integrations.billavenue.errors import BillAvenueClientError
from apps.integrations.bbps_client import BBPSClient
from apps.integrations.models import (
    BillAvenueAgentProfile,
    BillAvenueConfig,
    BillAvenueModeChannelPolicy,
)


def _default_agent_id() -> str:
    cfg = BillAvenueConfig.objects.filter(is_deleted=False, enabled=True, is_active=True).first()
    if not cfg:
        return ''
    row = (
        BillAvenueAgentProfile.objects.filter(config=cfg, is_deleted=False, enabled=True)
        .order_by('name')
        .first()
    )
    return str(row.agent_id).strip() if row else ''


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_categories_view(request):
    """
    Get bill categories.
    GET /api/bbps/categories/
    """
    categories = get_bill_categories()
    return Response({
        'success': True,
        'data': {'categories': categories},
        'message': 'Categories retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_billers_view(request, category):
    """
    Get billers for a category.
    GET /api/bbps/billers/{category}/
    """
    billers = get_billers_by_category(category)
    return Response({
        'success': True,
        'data': {'billers': billers},
        'message': 'Billers retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_providers_view(request, category):
    """Get providers mapped for a category."""
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response({'success': False, 'data': None, 'message': 'Provider governance is disabled', 'errors': []}, status=503)
    providers = get_providers_by_category(category)
    return Response(
        {
            'success': True,
            'data': {'providers': providers},
            'message': 'Providers retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def biller_schema_view(request, biller_id):
    schema = get_biller_input_schema(biller_id)
    return Response(
        {
            'success': True,
            'data': {'biller_id': biller_id, 'input_schema': schema},
            'message': 'Biller schema retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quote_view(request):
    payload = request.data or {}
    amount = payload.get('amount')
    biller_id = str(payload.get('biller_id') or '').strip()
    bill_type = str(payload.get('bill_type') or '').strip()
    provider_id = payload.get('provider_id')
    if amount in (None, ''):
        return Response({'success': False, 'data': None, 'message': 'amount is required', 'errors': []}, status=400)
    if not biller_id:
        return Response({'success': False, 'data': None, 'message': 'biller_id is required', 'errors': []}, status=400)
    readiness = governance_readiness_for_biller(biller_id)
    if not readiness.get('allowed'):
        return Response({'success': False, 'data': None, 'message': 'Service unavailable until admin approval', 'errors': readiness.get('blocked_by', [])}, status=400)
    try:
        amount_dec = Decimal(str(amount))
        if amount_dec <= 0:
            raise ValueError('invalid amount')
        c = resolve_commission_for_payment(
            amount=amount_dec,
            bill_data={'biller_id': biller_id, 'bill_type': bill_type, 'provider_id': provider_id},
        )
        applied_charge = c.get('charge')
        computed_charge = c.get('computed_charge')
        if not getattr(settings, 'BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED', False):
            applied_charge = Decimal(str(getattr(settings, 'BBPS_SERVICE_CHARGE', 0)))
        total = amount_dec + Decimal(str(applied_charge))
        return Response(
            {
                'success': True,
                'data': {
                    'amount': float(amount_dec),
                    'computed_charge': float(computed_charge),
                    'applied_charge': float(applied_charge),
                    'total_deducted': float(total),
                    'shadow_mode': not bool(getattr(settings, 'BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED', False)),
                    'commission_rule_code': c.get('commission_rule_code') or '',
                    'commission_rule_snapshot': c.get('commission_rule_snapshot') or {},
                },
                'message': 'Quote generated successfully',
                'errors': [],
            },
            status=200,
        )
    except Exception:
        return Response({'success': False, 'data': None, 'message': 'Invalid quote request', 'errors': []}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def setup_readiness_view(request):
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response({'success': False, 'data': None, 'message': 'Provider governance is disabled', 'errors': []}, status=503)
    return Response(
        {
            'success': True,
            'data': get_setup_readiness(),
            'message': 'BBPS setup readiness retrieved successfully',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def fetch_bill_view(request):
    """
    Fetch bill details.
    POST /api/bbps/fetch-bill/
    """
    serializer = FetchBillSerializer(data=request.data)
    if serializer.is_valid():
        try:
            biller_id = serializer.validated_data.get('biller_id') or ''
            if not biller_id:
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'biller_id is required for live BillAvenue bill fetch',
                    'errors': []
                }, status=status.HTTP_400_BAD_REQUEST)
            readiness = governance_readiness_for_biller(biller_id)
            if not readiness.get('allowed'):
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'Service unavailable until admin approval',
                    'errors': readiness.get('blocked_by', []),
                }, status=status.HTTP_400_BAD_REQUEST)

            input_map = {}
            raw_input_params = serializer.validated_data.get('input_params') or []
            if isinstance(raw_input_params, list):
                for row in raw_input_params:
                    if not isinstance(row, dict):
                        continue
                    key = str(row.get('paramName') or row.get('param_name') or '').strip()
                    val = row.get('paramValue') if 'paramValue' in row else row.get('param_value')
                    if key and val not in (None, ''):
                        input_map[key] = str(val)
            # Backward-compatible aliases (used when client has not switched to metadata-driven schema yet)
            if not input_map and serializer.validated_data.get('customer_number'):
                input_map['Customer Number'] = serializer.validated_data.get('customer_number')
            if not input_map and serializer.validated_data.get('mobile'):
                input_map['Mobile Number'] = serializer.validated_data.get('mobile')
            if not input_map and serializer.validated_data.get('card_last4'):
                input_map['Card Last4 Digits'] = serializer.validated_data.get('card_last4')

            validate_biller_inputs(biller_id=biller_id, input_map=input_map)
            flow = fetch_bill_with_cache(
                user=request.user,
                biller_id=biller_id,
                customer_info={'customerMobile': serializer.validated_data.get('mobile') or ''},
                input_params=[{'paramName': k, 'paramValue': v} for k, v in input_map.items()],
                agent_device_info={
                    'initChannel': 'AGT',
                    'ip': request.META.get('REMOTE_ADDR') or '',
                },
                agent_id=_default_agent_id(),
                biller_adhoc=False,
            )
            result = flow['bill_result']
            return Response({
                'success': True,
                'data': {'bill': result, 'fetch_session_id': flow['fetch_session'].pk},
                'message': 'Bill fetched successfully',
                'errors': []
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'data': None,
                'message': f'Failed to fetch bill: {str(e)}',
                'errors': []
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'success': False,
        'data': None,
        'message': 'Failed to fetch bill',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pay_bill_view(request):
    """
    Process bill payment.
    POST /api/bbps/pay/
    """
    assert_can_perform_financial_txn(request.user)
    serializer = BillPaymentCreateSerializer(data=request.data)
    if serializer.is_valid():
        try:
            payload = dict(serializer.validated_data)
            if payload.get('biller_id'):
                readiness = governance_readiness_for_biller(payload.get('biller_id'))
                if not readiness.get('allowed'):
                    return Response({
                        'success': False,
                        'data': None,
                        'message': 'Service unavailable until admin approval',
                        'errors': readiness.get('blocked_by', []),
                    }, status=status.HTTP_400_BAD_REQUEST)
                if payload.get('service_id') in (None, ''):
                    payload['service_id'] = f"PMBBPS{timezone.now().strftime('%Y%m%d%H%M%S')}"
                if not payload.get('agent_id'):
                    payload['agent_id'] = _default_agent_id()
                result = process_bill_payment_flow(user=request.user, bill_data=payload)
                bill_payment = result.get('bill_payment')
            else:
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'biller_id is required for live BillAvenue payment',
                    'errors': []
                }, status=status.HTTP_400_BAD_REQUEST)
            response_data = BillPaymentSerializer(bill_payment).data if bill_payment else None
            return Response({
                'success': True,
                'data': {'bill_payment': response_data},
                'message': 'Bill payment processed successfully',
                'errors': []
            }, status=status.HTTP_201_CREATED)
        except (InsufficientBalance, TransactionFailed) as e:
            return Response({
                'success': False,
                'data': None,
                'message': str(e),
                'errors': []
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'success': False,
        'data': None,
        'message': 'Bill payment failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bill_payments_list_view(request):
    """
    List bill payments (My Bills).
    GET /api/bbps/payments/
    """
    payments = BillPayment.objects.filter(user=request.user).order_by('-created_at')
    
    # Filters
    status_filter = request.query_params.get('status')
    if status_filter:
        payments = payments.filter(status=status_filter)
    
    # Pagination
    page_size = 20
    page = int(request.query_params.get('page', 1))
    start = (page - 1) * page_size
    end = start + page_size
    
    paginated_payments = payments[start:end]
    serializer = BillPaymentSerializer(paginated_payments, many=True)
    
    return Response({
        'success': True,
        'data': {
            'payments': serializer.data,
            'total': payments.count(),
            'page': page,
            'page_size': page_size
        },
        'message': 'Bill payments retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bill_payment_detail_view(request, payment_id):
    """
    Get bill payment details.
    GET /api/bbps/payments/{id}/
    """
    try:
        payment = BillPayment.objects.get(id=payment_id, user=request.user)
        serializer = BillPaymentSerializer(payment)
        return Response({
            'success': True,
            'data': {'payment': serializer.data},
            'message': 'Bill payment retrieved successfully',
            'errors': []
        }, status=status.HTTP_200_OK)
    except BillPayment.DoesNotExist:
        return Response({
            'success': False,
            'data': None,
            'message': 'Bill payment not found',
            'errors': []
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def billavenue_config_view(request):
    config = BillAvenueConfig.objects.filter(is_deleted=False, is_active=True).order_by('-updated_at').first() or BillAvenueConfig.objects.filter(is_deleted=False).order_by('-updated_at').first()
    if request.method == 'GET':
        return Response(
            {
                'success': True,
                'data': {'config': BillAvenueConfigSerializer(config).data if config else None},
                'message': 'BillAvenue config retrieved successfully',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    data = dict(request.data)
    if config:
        ser = BillAvenueConfigSerializer(config, data=data, partial=True)
    else:
        ser = BillAvenueConfigSerializer(data=data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid config', 'errors': ser.errors}, status=400)
    incoming_mode = str(ser.validated_data.get('mode') or '').lower()
    if incoming_mode == 'mock':
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Mock mode is disabled. Use UAT or PROD mode.',
                'errors': [],
            },
            status=400,
        )
    cfg = ser.save()
    if cfg.is_active:
        BillAvenueConfig.objects.exclude(pk=cfg.pk).update(is_active=False)
        if cfg.activated_at is None:
            cfg.activated_at = timezone.now()
            cfg.activated_by = request.user
            cfg.save(update_fields=['activated_at', 'activated_by'])
    return Response({'success': True, 'data': {'config': BillAvenueConfigSerializer(cfg).data}, 'message': 'BillAvenue config saved', 'errors': []}, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def billavenue_config_secrets_view(request):
    config = BillAvenueConfig.objects.filter(is_deleted=False, is_active=True).order_by('-updated_at').first() or BillAvenueConfig.objects.filter(is_deleted=False).order_by('-updated_at').first()
    if not config:
        return Response({'success': False, 'data': None, 'message': 'Create config first', 'errors': []}, status=400)
    ser = BillAvenueSecretUpdateSerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid secrets', 'errors': ser.errors}, status=400)
    val = ser.validated_data
    # Only set non-empty values so a partial form submit does not wipe existing secrets.
    if 'working_key' in val and (val.get('working_key') or '').strip():
        config.set_working_key((val.get('working_key') or '').strip())
    if 'iv' in val and (val.get('iv') or '').strip():
        config.set_iv((val.get('iv') or '').strip())
    if 'callback_secret' in val and (val.get('callback_secret') or '').strip():
        config.set_callback_secret((val.get('callback_secret') or '').strip())
    config.save(update_fields=['working_key_encrypted', 'iv_encrypted', 'callback_secret_encrypted', 'updated_at'])
    return Response(
        {
            'success': True,
            'data': {'config': BillAvenueConfigSerializer(config).data},
            'message': 'BillAvenue secrets updated',
            'errors': [],
        },
        status=200,
    )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def billavenue_agent_profiles_view(request):
    if request.method == 'GET':
        rows = BillAvenueAgentProfile.objects.filter(is_deleted=False).order_by('-created_at')
        return Response({'success': True, 'data': {'profiles': BillAvenueAgentProfileSerializer(rows, many=True).data}, 'message': 'Agent profiles retrieved successfully', 'errors': []}, status=200)
    obj = None
    req_id = request.data.get('id')
    if req_id:
        obj = BillAvenueAgentProfile.objects.filter(pk=req_id, is_deleted=False).first()
    if obj is None:
        cfg_id = request.data.get('config')
        name = str(request.data.get('name') or '').strip()
        if cfg_id and name:
            obj = BillAvenueAgentProfile.objects.filter(config_id=cfg_id, name=name, is_deleted=False).first()
    ser = BillAvenueAgentProfileSerializer(obj, data=request.data, partial=bool(obj)) if obj else BillAvenueAgentProfileSerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid agent profile', 'errors': ser.errors}, status=400)
    try:
        row = ser.save()
    except IntegrityError:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Agent profile with this config and name already exists. Edit the existing profile instead of creating duplicate.',
                'errors': [],
            },
            status=400,
        )
    except Exception as exc:
        # Return a safe, debuggable error instead of 500.
        return Response(
            {
                'success': False,
                'data': None,
                'message': f'Failed to save agent profile: {exc}',
                'errors': [],
            },
            status=400,
        )
    return Response({'success': True, 'data': {'profile': BillAvenueAgentProfileSerializer(row).data}, 'message': 'Agent profile saved', 'errors': []}, status=200 if obj else 201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def billavenue_mode_channel_policies_view(request):
    if request.method == 'GET':
        rows = BillAvenueModeChannelPolicy.objects.filter(is_deleted=False).order_by('-created_at')
        return Response({'success': True, 'data': {'policies': BillAvenueModeChannelPolicySerializer(rows, many=True).data}, 'message': 'Mode/channel policies retrieved successfully', 'errors': []}, status=200)
    ser = BillAvenueModeChannelPolicySerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid policy', 'errors': ser.errors}, status=400)
    row = ser.save()
    return Response({'success': True, 'data': {'policy': BillAvenueModeChannelPolicySerializer(row).data}, 'message': 'Mode/channel policy saved', 'errors': []}, status=201)


def _as_audit_snapshot(rule: BbpsCategoryCommissionRule) -> dict:
    return {
        'id': rule.pk,
        'category_id': rule.category_id,
        'rule_code': rule.rule_code,
        'commission_type': rule.commission_type,
        'value': str(rule.value),
        'min_commission': str(rule.min_commission),
        'max_commission': str(rule.max_commission),
        'is_active': rule.is_active,
        'effective_from': rule.effective_from.isoformat() if rule.effective_from else None,
        'effective_to': rule.effective_to.isoformat() if rule.effective_to else None,
        'notes': rule.notes,
    }


def _invalidate_provider_cache(*category_codes: str):
    for code in category_codes:
        if code:
            cache.delete(f"bbps:providers:{normalize_category_code(code)}")


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def integration_health_view(request):
    cfg = BillAvenueConfig.objects.filter(is_deleted=False, enabled=True, is_active=True).first()
    profile_count = BillAvenueAgentProfile.objects.filter(
        is_deleted=False,
        enabled=True,
        config=cfg,
    ).count() if cfg else 0
    has_base_url = bool(str(getattr(cfg, 'base_url', '') or '').strip()) if cfg else False
    has_access_code = bool(str(getattr(cfg, 'access_code', '') or '').strip()) if cfg else False
    has_institute_id = bool(str(getattr(cfg, 'institute_id', '') or '').strip()) if cfg else False
    has_working_key = bool(str(getattr(cfg, 'working_key_encrypted', '') or '').strip()) if cfg else False
    has_iv = bool(str(getattr(cfg, 'iv_encrypted', '') or '').strip()) if cfg else False
    stale_billers = BbpsBillerMaster.objects.filter(is_deleted=False, is_stale=True).count()
    unmapped_billers = BbpsBillerMaster.objects.filter(is_deleted=False).exclude(
        provider_maps__is_deleted=False,
        provider_maps__is_active=True,
    ).count()
    last_mdm_audit = (
        BbpsApiAuditLog.objects.filter(endpoint_name='biller_info', is_deleted=False)
        .order_by('-created_at')
        .first()
    )
    latest_failed = (
        BbpsApiAuditLog.objects.filter(is_deleted=False, success=False)
        .order_by('-created_at')
        .first()
    )
    entitlement_issue = ''
    if last_mdm_audit and not last_mdm_audit.success:
        msg = str(last_mdm_audit.error_message or '')
        if 'access denied' in msg.lower() or 'unauthorized' in msg.lower():
            entitlement_issue = msg or 'BillAvenue entitlement denied for biller_info.'
    probe_enabled = str(request.query_params.get('probe', '1')).strip().lower() not in ('0', 'false', 'no')
    probe_ok = None
    probe_message = ''
    if probe_enabled and cfg and profile_count > 0:
        try:
            probe_client = BBPSClient()
            probe_agent = (
                BillAvenueAgentProfile.objects.filter(config=cfg, is_deleted=False, enabled=True)
                .order_by('name')
                .first()
            )
            payload = {'agentId': str(probe_agent.agent_id or '').strip()} if probe_agent else {}
            probe_client.biller_info(payload)
            probe_ok = True
        except BillAvenueClientError as exc:
            probe_ok = False
            probe_message = str(exc)
        except Exception as exc:
            probe_ok = False
            probe_message = f'Probe failed: {exc}'

    checks = [
        {'key': 'active_config', 'ok': bool(cfg)},
        {'key': 'config_url', 'ok': has_base_url},
        {'key': 'credentials', 'ok': has_access_code and has_institute_id and has_working_key and has_iv},
        {'key': 'agent_profile', 'ok': profile_count > 0},
    ]
    if probe_ok is not None:
        checks.append({'key': 'entitlement_probe', 'ok': bool(probe_ok)})
    blockers = [c['key'] for c in checks if not c['ok']]
    return Response(
        {
            'success': True,
            'data': {
                'checks': checks,
                'blockers': blockers,
                'stale_billers': stale_billers,
                'unmapped_billers': unmapped_billers,
                'entitlement_issue': entitlement_issue,
                'entitlement_probe_ok': probe_ok,
                'entitlement_probe_message': probe_message,
                'latest_mdm_audit': {
                    'success': bool(last_mdm_audit.success) if last_mdm_audit else None,
                    'status_code': str(last_mdm_audit.status_code or '') if last_mdm_audit else '',
                    'error_message': str(last_mdm_audit.error_message or '') if last_mdm_audit else '',
                },
                'latest_failed_request': {
                    'endpoint_name': str(latest_failed.endpoint_name or '') if latest_failed else '',
                    'request_id': str(latest_failed.request_id or '') if latest_failed else '',
                    'status_code': str(latest_failed.status_code or '') if latest_failed else '',
                    'error_message': str(latest_failed.error_message or '') if latest_failed else '',
                    'request_meta': latest_failed.request_meta if latest_failed else {},
                },
                'go_live_blocked': bool(blockers or stale_billers or unmapped_billers),
            },
            'message': 'BillAvenue integration health retrieved successfully',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def refresh_provider_cache_view(request):
    category_code = str(request.data.get('category_code') or '').strip()
    if category_code:
        _invalidate_provider_cache(category_code)
    else:
        rows = BbpsServiceCategory.objects.filter(is_deleted=False).values_list('code', flat=True)
        for code in rows:
            _invalidate_provider_cache(code)
    return Response({'success': True, 'data': {'category_code': category_code or None}, 'message': 'Provider cache refreshed', 'errors': []}, status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def governance_ops_summary_view(request):
    stale_billers = BbpsBillerMaster.objects.filter(is_deleted=False, is_stale=True).count()
    unmapped_billers = BbpsBillerMaster.objects.filter(is_deleted=False).exclude(
        provider_maps__is_deleted=False,
        provider_maps__is_active=True,
    ).count()
    inactive_categories = BbpsServiceCategory.objects.filter(is_deleted=False, is_active=False).count()
    missing_rule_categories = list(
        BbpsServiceCategory.objects.filter(is_deleted=False, is_active=True)
        .exclude(commission_rules__is_deleted=False, commission_rules__is_active=True)
        .values_list('code', flat=True)
    )
    conflicting_rules = 0
    # lightweight conflict check per category
    for cat in BbpsServiceCategory.objects.filter(is_deleted=False, is_active=True):
        rows = list(
            BbpsCategoryCommissionRule.objects.filter(
                is_deleted=False,
                is_active=True,
                category=cat,
            ).order_by('effective_from')
        )
        for i, r1 in enumerate(rows):
            for r2 in rows[i + 1 :]:
                if (r1.effective_to is None or r2.effective_from is None or r2.effective_from <= r1.effective_to) and (
                    r2.effective_to is None or r1.effective_from is None or r1.effective_from <= r2.effective_to
                ):
                    conflicting_rules += 1
                    break
    return Response(
        {
            'success': True,
            'data': {
                'stale_billers': stale_billers,
                'unmapped_billers': unmapped_billers,
                'inactive_categories': inactive_categories,
                'categories_missing_active_rule': missing_rule_categories,
                'conflicting_rule_windows': conflicting_rules,
            },
            'message': 'Governance ops summary retrieved successfully',
            'errors': [],
        },
        status=200,
    )


def _approval_status(entity) -> str:
    if not hasattr(entity, 'metadata'):
        return 'approved' if getattr(entity, 'is_active', False) else 'pending'
    md = dict(getattr(entity, 'metadata', {}) or {})
    status = str(md.get('approval_status') or '').strip().lower()
    if status in ('pending', 'approved', 'rejected'):
        return status
    return 'approved' if getattr(entity, 'is_active', False) else 'pending'


def _set_approval_status(entity, status_value: str):
    if not hasattr(entity, 'metadata'):
        return
    md = dict(getattr(entity, 'metadata', {}) or {})
    md['approval_status'] = status_value
    entity.metadata = md


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def service_categories_view(request):
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response({'success': False, 'data': None, 'message': 'Provider governance is disabled', 'errors': []}, status=503)
    if request.method == 'GET':
        rows = BbpsServiceCategory.objects.filter(is_deleted=False).order_by('display_order', 'name')
        status_filter = str(request.query_params.get('approval') or '').strip().lower()
        if status_filter in ('pending', 'approved', 'rejected'):
            rows = [r for r in rows if _approval_status(r) == status_filter]
        return Response(
            {
                'success': True,
                'data': {'categories': BbpsServiceCategorySerializer(rows, many=True).data},
                'message': 'Service categories retrieved successfully',
                'errors': [],
            },
            status=200,
        )
    obj = None
    if request.data.get('id'):
        obj = BbpsServiceCategory.objects.filter(pk=request.data.get('id'), is_deleted=False).first()
    ser = BbpsServiceCategorySerializer(obj, data=request.data, partial=bool(obj)) if obj else BbpsServiceCategorySerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid service category', 'errors': ser.errors}, status=400)
    row = ser.save()
    _set_approval_status(row, 'approved' if row.is_active else 'pending')
    _invalidate_provider_cache(row.code)
    return Response({'success': True, 'data': {'category': BbpsServiceCategorySerializer(row).data}, 'message': 'Service category saved', 'errors': []}, status=200 if obj else 201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def service_providers_view(request):
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response({'success': False, 'data': None, 'message': 'Provider governance is disabled', 'errors': []}, status=503)
    if request.method == 'GET':
        rows = BbpsServiceProvider.objects.filter(is_deleted=False).select_related('category').order_by('category__display_order', 'priority', 'name')
        status_filter = str(request.query_params.get('approval') or '').strip().lower()
        if status_filter in ('pending', 'approved', 'rejected'):
            rows = [r for r in rows if _approval_status(r) == status_filter]
        return Response(
            {
                'success': True,
                'data': {'providers': BbpsServiceProviderSerializer(rows, many=True).data},
                'message': 'Service providers retrieved successfully',
                'errors': [],
            },
            status=200,
        )
    obj = None
    if request.data.get('id'):
        obj = BbpsServiceProvider.objects.filter(pk=request.data.get('id'), is_deleted=False).first()
    ser = BbpsServiceProviderSerializer(obj, data=request.data, partial=bool(obj)) if obj else BbpsServiceProviderSerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid service provider', 'errors': ser.errors}, status=400)
    action = str(request.data.get('action') or '').strip().lower()
    if obj and action in ('approve', 'reject', 'toggle'):
        if action == 'approve':
            obj.is_active = True
            _set_approval_status(obj, 'approved')
        elif action == 'reject':
            obj.is_active = False
            _set_approval_status(obj, 'rejected')
        else:
            obj.is_active = not bool(obj.is_active)
            _set_approval_status(obj, 'approved' if obj.is_active else 'pending')
        obj.save(update_fields=['is_active', 'metadata', 'updated_at'])
        row = obj
    else:
        row = ser.save()
        _set_approval_status(row, 'approved' if row.is_active else 'pending')
        row.save(update_fields=['metadata', 'updated_at'])
    _invalidate_provider_cache(row.category.code if row.category else '')
    return Response({'success': True, 'data': {'provider': BbpsServiceProviderSerializer(row).data}, 'message': 'Service provider saved', 'errors': []}, status=200 if obj else 201)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def provider_biller_maps_view(request):
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response({'success': False, 'data': None, 'message': 'Provider governance is disabled', 'errors': []}, status=503)
    if request.method == 'GET':
        rows = BbpsProviderBillerMap.objects.filter(is_deleted=False).select_related('provider__category', 'biller_master').order_by('provider__category__display_order', 'provider__priority', 'priority')
        status_filter = str(request.query_params.get('approval') or '').strip().lower()
        if status_filter in ('pending', 'approved', 'rejected'):
            rows = [r for r in rows if _approval_status(r) == status_filter]
        payload = []
        for row in rows:
            entry = BbpsProviderBillerMapSerializer(row).data
            entry['blocked_by'] = governance_block_reasons_for_map(row)
            entry['approval_status'] = _approval_status(row)
            payload.append(entry)
        return Response(
            {
                'success': True,
                'data': {'maps': payload},
                'message': 'Provider-biller maps retrieved successfully',
                'errors': [],
            },
            status=200,
        )
    action = str(request.data.get('action') or '').strip().lower()
    if action == 'bulk_approve':
        ids = request.data.get('ids') or []
        qs = BbpsProviderBillerMap.objects.filter(is_deleted=False, id__in=ids).select_related('provider__category', 'biller_master')
        changed = 0
        blocked = []
        for row in qs:
            reasons = governance_block_reasons_for_map(row)
            reasons = [r for r in reasons if r not in ('map_inactive', 'provider_inactive', 'category_inactive')]
            if reasons:
                blocked.append({'id': row.id, 'blocked_by': reasons})
                continue
            row.is_active = True
            if not row.provider.is_active:
                row.provider.is_active = True
                _set_approval_status(row.provider, 'approved')
                row.provider.save(update_fields=['is_active', 'metadata', 'updated_at'])
            if not row.provider.category.is_active:
                row.provider.category.is_active = True
                _set_approval_status(row.provider.category, 'approved')
                row.provider.category.save(update_fields=['is_active', 'metadata', 'updated_at'])
            _set_approval_status(row, 'approved')
            row.save(update_fields=['is_active', 'metadata', 'updated_at'])
            changed += 1
            _invalidate_provider_cache(row.provider.category.code)
        return Response({'success': True, 'data': {'approved_count': changed, 'blocked': blocked}, 'message': 'Bulk approve completed', 'errors': []}, status=200)
    obj = None
    if request.data.get('id'):
        obj = BbpsProviderBillerMap.objects.filter(pk=request.data.get('id'), is_deleted=False).first()
    ser = BbpsProviderBillerMapSerializer(obj, data=request.data, partial=bool(obj)) if obj else BbpsProviderBillerMapSerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid provider-biller map', 'errors': ser.errors}, status=400)
    if obj and action in ('approve', 'reject', 'toggle'):
        if action == 'approve':
            obj.is_active = True
            if not obj.provider.is_active:
                obj.provider.is_active = True
                _set_approval_status(obj.provider, 'approved')
                obj.provider.save(update_fields=['is_active', 'metadata', 'updated_at'])
            if not obj.provider.category.is_active:
                obj.provider.category.is_active = True
                _set_approval_status(obj.provider.category, 'approved')
                obj.provider.category.save(update_fields=['is_active', 'metadata', 'updated_at'])
            _set_approval_status(obj, 'approved')
        elif action == 'reject':
            obj.is_active = False
            _set_approval_status(obj, 'rejected')
        else:
            obj.is_active = not bool(obj.is_active)
            _set_approval_status(obj, 'approved' if obj.is_active else 'pending')
        obj.save(update_fields=['is_active', 'metadata', 'updated_at'])
        row = obj
    else:
        row = ser.save()
        _set_approval_status(row, 'approved' if row.is_active else 'pending')
        row.save(update_fields=['metadata', 'updated_at'])
    _invalidate_provider_cache(row.provider.category.code if row.provider and row.provider.category else '')
    return Response({'success': True, 'data': {'map': BbpsProviderBillerMapSerializer(row).data}, 'message': 'Provider-biller map saved', 'errors': []}, status=200 if obj else 201)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_master_admin_view(request):
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response({'success': False, 'data': None, 'message': 'Provider governance is disabled', 'errors': []}, status=503)
    category = request.query_params.get('category')
    qs = BbpsBillerMaster.objects.filter(is_deleted=False).order_by('biller_name')
    if category:
        qs = qs.filter(biller_category__icontains=category)
    rows = qs[:500]
    return Response(
        {
            'success': True,
            'data': {'billers': BbpsBillerMasterLiteSerializer(rows, many=True).data},
            'message': 'Biller master retrieved successfully',
            'errors': [],
        },
        status=200,
    )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def commission_rules_view(request):
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response({'success': False, 'data': None, 'message': 'Provider governance is disabled', 'errors': []}, status=503)
    if request.method == 'GET':
        include_seeded = str(request.query_params.get('include_seeded') or '').strip().lower() in ('1', 'true', 'yes')
        rows = BbpsCategoryCommissionRule.objects.filter(is_deleted=False).select_related('category').order_by('-is_active', '-effective_from', '-created_at')
        if not include_seeded:
            rows = rows.exclude(is_active=False, notes='Seeded default rule')
        return Response(
            {
                'success': True,
                'data': {'rules': BbpsCategoryCommissionRuleSerializer(rows, many=True).data},
                'message': 'Commission rules retrieved successfully',
                'errors': [],
            },
            status=200,
        )
    obj = None
    previous_snapshot = {}
    if request.data.get('id'):
        obj = BbpsCategoryCommissionRule.objects.filter(pk=request.data.get('id'), is_deleted=False).first()
        if obj:
            previous_snapshot = _as_audit_snapshot(obj)
    ser = BbpsCategoryCommissionRuleSerializer(obj, data=request.data, partial=bool(obj)) if obj else BbpsCategoryCommissionRuleSerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid commission rule', 'errors': ser.errors}, status=400)
    row = ser.save()
    BbpsCommissionAudit.objects.create(
        rule=row,
        changed_by_user_id=request.user.pk if request.user and request.user.is_authenticated else None,
        action='update' if obj else 'create',
        previous_snapshot=previous_snapshot,
        new_snapshot=_as_audit_snapshot(row),
        reason=str(request.data.get('reason') or ''),
    )
    _invalidate_provider_cache(row.category.code if row.category else '')
    return Response({'success': True, 'data': {'rule': BbpsCategoryCommissionRuleSerializer(row).data}, 'message': 'Commission rule saved', 'errors': []}, status=200 if obj else 201)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def commission_audit_view(request):
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response({'success': False, 'data': None, 'message': 'Provider governance is disabled', 'errors': []}, status=503)
    rule_id = request.query_params.get('rule_id')
    rows = BbpsCommissionAudit.objects.filter(is_deleted=False).select_related('rule').order_by('-created_at')
    if rule_id:
        rows = rows.filter(rule_id=rule_id)
    payload = [
        {
            'id': r.pk,
            'rule_id': r.rule_id,
            'rule_code': r.rule.rule_code if r.rule_id else '',
            'changed_by_user_id': r.changed_by_user_id,
            'action': r.action,
            'reason': r.reason,
            'previous_snapshot': r.previous_snapshot,
            'new_snapshot': r.new_snapshot,
            'created_at': r.created_at,
        }
        for r in rows[:300]
    ]
    return Response({'success': True, 'data': {'audits': payload}, 'message': 'Commission audits retrieved successfully', 'errors': []}, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def sync_billers_view(request):
    ser = BillerSyncRequestSerializer(data=request.data or {})
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid sync request', 'errors': ser.errors}, status=400)
    try:
        out = sync_biller_info(ser.validated_data.get('biller_ids') or [])
        return Response({'success': True, 'data': out, 'message': 'Biller sync completed', 'errors': []}, status=200)
    except BillAvenueClientError as e:
        return Response({'success': False, 'data': None, 'message': str(e), 'errors': []}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def poll_status_view(request):
    ser = StatusPollSerializer(data=request.data or {})
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid poll request', 'errors': ser.errors}, status=400)
    attempt = None
    if ser.validated_data.get('attempt_id'):
        attempt = BbpsPaymentAttempt.objects.filter(pk=ser.validated_data['attempt_id'], is_deleted=False).first()
    elif ser.validated_data.get('request_id'):
        attempt = BbpsPaymentAttempt.objects.filter(request_id=ser.validated_data['request_id'], is_deleted=False).order_by('-created_at').first()
    elif ser.validated_data.get('txn_ref_id'):
        attempt = BbpsPaymentAttempt.objects.filter(txn_ref_id=ser.validated_data['txn_ref_id'], is_deleted=False).order_by('-created_at').first()
    if not attempt:
        return Response({'success': False, 'data': None, 'message': 'Attempt not found', 'errors': []}, status=404)
    try:
        updated = poll_attempt_status(attempt)
    except TransactionFailed as exc:
        return Response({'success': False, 'data': None, 'message': str(exc), 'errors': []}, status=400)
    return Response({'success': True, 'data': {'attempt_id': updated.pk, 'status': updated.status}, 'message': 'Status polled', 'errors': []}, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def transaction_query_view(request):
    ser = TransactionQuerySerializer(data=request.data or {})
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid transaction query', 'errors': ser.errors}, status=400)
    payload = {
        'trackingType': ser.validated_data['tracking_type'],
        'trackingValue': ser.validated_data['tracking_value'],
    }
    if ser.validated_data.get('from_date'):
        payload['fromDate'] = ser.validated_data.get('from_date')
    if ser.validated_data.get('to_date'):
        payload['toDate'] = ser.validated_data.get('to_date')
    try:
        client = BBPSClient()
        data = client.transaction_status(
            track_type=payload['trackingType'],
            track_value=payload['trackingValue'],
            from_date=str(payload.get('fromDate') or ''),
            to_date=str(payload.get('toDate') or ''),
        )
    except BillAvenueClientError as exc:
        return Response({'success': False, 'data': None, 'message': str(exc), 'errors': []}, status=400)
    txns = data.get('txnList') or data.get('transactionStatusResp', {}).get('txnList') or []
    return Response(
        {
            'success': True,
            'data': {'transactions': txns, 'raw': data},
            'message': 'Transaction query completed',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complaint_register_view(request):
    ser = ComplaintRegisterSerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid complaint request', 'errors': ser.errors}, status=400)
    try:
        row = register_complaint(user=request.user, **ser.validated_data)
    except TransactionFailed as exc:
        return Response({'success': False, 'data': None, 'message': str(exc), 'errors': []}, status=400)
    return Response({'success': True, 'data': {'complaint_id': row.complaint_id, 'status': row.complaint_status}, 'message': 'Complaint registered', 'errors': []}, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complaint_track_view(request):
    ser = ComplaintTrackSerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid complaint track request', 'errors': ser.errors}, status=400)
    complaint = BbpsComplaint.objects.filter(complaint_id=ser.validated_data['complaint_id'], user=request.user, is_deleted=False).first()
    if not complaint:
        return Response({'success': False, 'data': None, 'message': 'Complaint not found', 'errors': []}, status=404)
    resp = track_complaint(complaint=complaint)
    return Response({'success': True, 'data': {'response': resp}, 'message': 'Complaint tracked', 'errors': []}, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def plan_pull_view(request):
    ser = PlanPullSerializer(data=request.data or {})
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid plan pull request', 'errors': ser.errors}, status=400)
    try:
        out = pull_biller_plans(biller_ids=ser.validated_data.get('biller_ids') or [])
        return Response({'success': True, 'data': out, 'message': 'Plan pull completed', 'errors': []}, status=200)
    except BillAvenueClientError as e:
        return Response({'success': False, 'data': None, 'message': str(e), 'errors': []}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def deposit_enquiry_view(request):
    ser = DepositEnquirySerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid deposit enquiry request', 'errors': ser.errors}, status=400)
    try:
        out = enquire_deposits(**ser.validated_data)
        return Response({'success': True, 'data': out, 'message': 'Deposit enquiry completed', 'errors': []}, status=200)
    except BillAvenueClientError as e:
        return Response({'success': False, 'data': None, 'message': str(e), 'errors': []}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def uat_readiness_checklist_view(request):
    health = integration_health_view(request).data.get('data', {})
    readiness = get_setup_readiness()
    checklist = [
        {'key': 'active_config', 'ok': 'active_config' not in health.get('blockers', [])},
        {'key': 'agent_profile', 'ok': 'agent_profile' not in health.get('blockers', [])},
        {'key': 'entitlement_probe', 'ok': bool(health.get('entitlement_probe_ok'))},
        {'key': 'mdm_synced', 'ok': readiness.get('stats', {}).get('mdm_biller_count', 0) > 0},
        {'key': 'provider_mapping', 'ok': readiness.get('stats', {}).get('mapping_count', 0) > 0},
    ]
    blockers = [c['key'] for c in checklist if not c['ok']]
    return Response(
        {
            'success': True,
            'data': {
                'checklist': checklist,
                'blockers': blockers,
                'go_live_blocked': bool(blockers),
                'latest_probe_message': health.get('entitlement_probe_message') or '',
                'latest_mdm_error': (health.get('latest_mdm_audit') or {}).get('error_message') or '',
            },
            'message': 'UAT readiness checklist retrieved',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([])
def billavenue_callback_view(request):
    raw = request.data or {}
    enc = raw.get('encRequest') or raw.get('enc_request') or ''
    cfg = BillAvenueConfig.objects.filter(is_active=True, enabled=True, is_deleted=False).first()
    plain_data = {}
    if cfg and enc:
        try:
            plain = decrypt_payload(str(enc), working_key=cfg.get_working_key(), iv=cfg.get_iv())
            plain_data = {'raw': plain}
        except Exception:
            plain_data = {'raw': str(enc)}
    else:
        plain_data = raw if isinstance(raw, dict) else {'raw': str(raw)}

    evt = BbpsPushWebhookEvent.objects.create(
        request_id=str(raw.get('requestId') or ''),
        txn_ref_id=str(raw.get('txnRefId') or ''),
        event_type='PAYMENT_STATUS',
        response_code=str(raw.get('responseCode') or ''),
        response_reason=str(raw.get('responseReason') or ''),
        payload=plain_data,
        processed=False,
    )
    attempt = BbpsPaymentAttempt.objects.filter(
        request_id=evt.request_id or '', is_deleted=False
    ).order_by('-created_at').first() or BbpsPaymentAttempt.objects.filter(
        txn_ref_id=evt.txn_ref_id or '', is_deleted=False
    ).order_by('-created_at').first()
    if attempt:
        code = str(raw.get('responseCode') or '')
        if code == '000':
            attempt.status = 'SUCCESS'
            if attempt.bill_payment:
                attempt.bill_payment.status = 'SUCCESS'
                attempt.bill_payment.save(update_fields=['status'])
        elif code == '300':
            attempt.status = 'REFUNDED'
            if attempt.bill_payment:
                attempt.bill_payment.status = 'FAILED'
                attempt.bill_payment.failure_reason = 'Refund callback received'
                attempt.bill_payment.save(update_fields=['status', 'failure_reason'])
        else:
            attempt.status = 'FAILED'
            if attempt.bill_payment:
                attempt.bill_payment.status = 'FAILED'
                attempt.bill_payment.failure_reason = 'Callback failure'
                attempt.bill_payment.save(update_fields=['status', 'failure_reason'])
        attempt.settled_at = timezone.now()
        attempt.save(update_fields=['status', 'settled_at', 'updated_at'])
    evt.processed = True
    evt.processed_at = timezone.now()
    evt.save(update_fields=['processed', 'processed_at', 'updated_at'])
    return Response({'success': True, 'data': None, 'message': 'callback accepted', 'errors': []}, status=200)
