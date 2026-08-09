"""
BBPS views for the mPayhub platform.
"""
import hashlib
import json
import logging
import re
import uuid

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q

from apps.bbps.models import (
    BbpsApiAuditLog,
    BbpsBillerAdditionalInfoSchema,
    BbpsBillerCcf1Config,
    BbpsBillerInputParam,
    BbpsBillerMaster,
    BbpsBillerPaymentChannelLimit,
    BbpsBillerPaymentModeLimit,
    BbpsBillerPlanMeta,
    BillPayment,
    BbpsCategoryCommissionRule,
    BbpsComplaint,
    BbpsCommissionAudit,
    BbpsPaymentAttempt,
    BbpsPlanPullRun,
    BbpsProviderBillerMap,
    BbpsPushWebhookEvent,
    BbpsServiceCategory,
    BbpsServiceProvider,
    BbpsSyncUsageLog,
    BbpsMdmImportJob,
    BbpsMdmImportItem,
)
from apps.bbps.api_response import bbps_error_response
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
    BbpsBillerMasterAdminSerializer,
    BbpsProviderBillerMapSerializer,
    BbpsSyncUsageLogSerializer,
    BbpsMdmImportJobSerializer,
    BbpsMdmImportItemSerializer,
    BbpsServiceCategorySerializer,
    BbpsServiceProviderSerializer,
    BillerSyncRequestSerializer,
    MdmCatalogPublishSerializer,
    ComplaintRegisterSerializer,
    ComplaintHistoryItemSerializer,
    ComplaintHistoryQuerySerializer,
    ComplaintTrackSerializer,
    DepositEnquirySerializer,
    PlanPullSerializer,
    StatusPollSerializer,
    TransactionQuerySerializer,
)
from apps.bbps.services import (
    governance_block_reasons_for_map,
    get_bill_categories,
    get_biller_additional_info_schema,
    get_biller_input_schema,
    get_biller_payment_ui_options,
    get_biller_plans_lite,
    get_billers_by_category,
    get_providers_by_category,
    get_setup_readiness,
    normalize_category_code,
)
from apps.bbps.mdm_param_utils import is_placeholder_style_param_name
from apps.bbps.catalog.env import (
    active_bbps_environment,
    biller_master_qs_for_env,
    catalog_cache_env_key,
    catalog_counts_by_environment,
    get_biller_master,
)
from apps.bbps.service_flow.bbps_wallet_charge import resolve_bbps_wallet_service_charge
from apps.integrations.billavenue.registry import (
    MODE_PRESETS,
    activate_billavenue_config,
    billavenue_credentials_missing,
    environments_summary,
    get_active_billavenue_config,
    get_billavenue_config_for_mode,
    get_or_create_billavenue_mode_row,
    normalize_billavenue_mode,
)
from apps.bbps.service_flow.commission_service import resolve_commission_for_payment
from apps.bbps.service_flow.mdm_sync_batch import (
    MdmSyncBatchError,
    MdmSyncQuotaExhausted,
    run_mdm_sync_batch,
    sync_quota_snapshot,
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
from apps.bbps.service_flow.validation_service import BbpsInputValidationError
from apps.bbps.service_flow.provider_float import BbpsProviderFloatInsufficient
from apps.bbps.error_catalog import provider_code_from_exception, resolve_bbps_error
from apps.bbps.service_flow.provider_policy import bootstrap_default_biller_policy_if_missing
from apps.bbps.service_flow.compliance import (
    bbps_channel_accepts_payment_mode,
    display_payment_modes_for_channel,
)
from apps.core.exceptions import InsufficientBalance, TransactionFailed
from apps.core.financial_access import assert_can_pay_out
from apps.core.maintenance_mode import MODULE_BBPS, assert_module_available
from apps.core.permissions import IsAdmin
from apps.integrations.billavenue.crypto import decrypt_payload
from apps.integrations.billavenue.errors import (
    BillAvenueClientError,
    BillAvenueEntitlementError,
    BillAvenueTransportError,
)

logger = logging.getLogger(__name__)
from apps.integrations.bbps_client import BBPSClient
from apps.integrations.models import (
    BillAvenueAgentProfile,
    BillAvenueConfig,
    BillAvenueModeChannelPolicy,
)


def _default_agent_id() -> str:
    cfg = get_active_billavenue_config()
    if not cfg:
        return ''
    row = (
        BillAvenueAgentProfile.objects.filter(config=cfg, is_deleted=False, enabled=True)
        .order_by('name')
        .first()
    )
    return str(row.agent_id).strip() if row else ''


def _friendly_pay_error_message(raw_message: str) -> str:
    msg = str(raw_message or '').strip()
    low = msg.lower()
    if not msg:
        return 'Payment failed. Please try again.'
    if 'timeout' in low or 'timed out' in low:
        return 'Bill payment is taking longer than usual at the provider. Please wait a moment and try again.'

    if 'agent_device_info missing required field' in low:
        return (
            'Selected payment method is not available for this biller in the current terminal flow. '
            'Please choose another payment method.'
        )
    if 'errorcode": "e077' in low or 'invalid for payment channel' in low:
        return 'Selected payment method is not supported for this biller right now. Please choose another method.'
    if 'e078' in low or 'payment channel:pos invalid' in low:
        return (
            'This biller does not accept the selected channel at the provider. '
            'Use Cash on the Agent (AGT) channel, fetch the bill again, then pay—or contact support if this continues.'
        )
    if 'e0378' in low:
        return (
            'Selected payment mode is not valid for the initiating channel. '
            'Try Cash on AGT, or fetch the bill again after changing the method.'
        )
    # BillAvenue often uses outer responseCode 204 for multiple inner errors — do not treat all as E204.
    if 'e212' in low or 'additionalinfo value mismatch' in low:
        return (
            'Extra bill details from the provider (additionalInfo) did not match this payment. '
            'Fetch the bill again and pay immediately without changing customer tags or plan. '
            'Custom amounts are allowed when the biller permits them.'
        )
    if 'e211' in low or 'billerresponse value mismatch' in low:
        return (
            'The bill snapshot sent to BillAvenue did not match your last successful fetch (billerResponse mismatch). '
            'Fetch the bill again, then pay immediately without changing amount, inputs, or plan selection.'
        )
    if 'e204' in low and ('already been used' in low or 'already been' in low):
        return 'This fetch reference is already consumed. Fetch the bill again before retrying payment.'
    if 'request id is already been used' in low:
        return 'This fetch reference is already consumed. Fetch the bill again before retrying payment.'
    if 'errorcode": "e210' in low or 'no fetch data found for given ref id' in low:
        return 'Fetch reference is not valid anymore. Please fetch the bill again and retry payment.'
    if 'errorcode": "e092' in low or 'remitter name required' in low:
        return 'Remitter details are missing. Update profile name and fetch bill again before payment.'

    provider_msg = re.search(r'"errorMessage"\s*:\s*"([^"]+)"', msg)
    if provider_msg:
        clean = provider_msg.group(1).strip()
        if clean:
            return clean
    return msg


def _friendly_fetch_error_message(raw_message: str) -> str:
    msg = str(raw_message or '').strip()
    low = msg.lower()
    if not msg:
        return 'Failed to fetch bill. Please try again.'
    if 'timeout' in low or 'timed out' in low:
        return 'Provider response timed out. Please retry in a few seconds.'
    if 'connection error' in low or 'max retries exceeded' in low or 'name or service not known' in low:
        return 'Provider network is temporarily unavailable. Please retry shortly.'
    if 've003' in low or 'agent id invalid' in low or 'agentid invalid' in low:
        return (
            'BillAvenue rejected the Agent ID for this live environment (VE003). '
            'Open BillAvenue Settings → edit the live environment → set the correct Production Agent ID from your BillAvenue pack, then retry.'
        )
    if 'errorcode": "bfr004' in low or 'no bill due' in low:
        return 'No bill is currently due for this account.'
    if 'errorcode": "bfr001' in low or 'invalid customer account' in low:
        return 'Customer account details are invalid. Please verify the entered account fields.'
    if 'errorcode": "brp046' in low or 'only quickpay permitted' in low or 'quickpay permitted' in low:
        return 'This biller supports QuickPay only. Bill fetch is not required; proceed with QuickPay payment.'
    if 'errorcode": "bfr' in low:
        provider_msg = re.search(r'"errorMessage"\s*:\s*"([^"]+)"', msg)
        if provider_msg:
            return provider_msg.group(1).strip() or 'Bill fetch failed.'
        return 'Unable to fetch bill for this account right now.'
    # Prefer provider suffix already attached by BillAvenue client: code=200 (VE003 — Agent ID invalid)
    m = re.search(r'code=\S+\s*\((.+)\)\s*$', msg)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return msg


def _friendly_plan_pull_error_message(raw_message: str) -> str:
    msg = str(raw_message or '').strip()
    low = msg.lower()
    if not msg:
        return 'Plan pull failed. Please try again.'
    if 'timeout' in low or 'timed out' in low:
        return 'Plan service response timed out. Please retry. If this continues, verify BillAvenue timeout settings.'
    if 'connection error' in low or 'max retries exceeded' in low or 'name or service not known' in low:
        return 'Unable to reach plan service right now. Please retry and verify provider connectivity.'
    if 'code=205' in low or 'entitlement' in low:
        return (
            'Plan pull is not enabled for this BillAvenue profile. '
            'Ask BillAvenue to enable Plan MDM (extPlanMDM) for your institute.'
        )
    if 'pp002' in low and 'invalid enc' in low:
        return (
            'BillAvenue rejected plan pull (PP002 Invalid ENC). '
            'Confirm Plan MDM is enabled for this institute, or re-check working key / IV with BillAvenue.'
        )
    if 'pp002' in low:
        return 'No plan data is available for this biller right now.'
    if 'agentid is required' in low:
        return 'Plan pull requires an active BillAvenue agent profile. Configure agentId in admin settings.'
    provider_msg = re.search(r'"errorMessage"\s*:\s*"([^"]+)"', msg)
    if provider_msg:
        clean = provider_msg.group(1).strip()
        if clean:
            return clean
    return msg


def _friendly_complaint_error_message(raw_message: str) -> str:
    msg = str(raw_message or '').strip()
    low = msg.lower()
    if not msg:
        return 'Complaint registration failed. Please try again.'
    if 'v5001' in low or 'invalid txnrefid format' in low:
        return 'Invalid B-Connect Transaction ID. Use the CC... reference shown on receipt/success screen.'
    if 'v5004' in low or 'description missing' in low:
        return 'Complaint description was rejected by provider. Please retry with a clear issue summary.'
    if (
        'complaint_register' in low
        and 'code=001' in low
        and (
            'unable to raise a new ticket' in low
            or 'unable to raise' in low
            and 'ticket' in low
            or 'the ticket is already' in low
            or 'ticket is already' in low
            or 'already open' in low
            or 'existing ticket' in low
            or 'complaint is already' in low
        )
    ):
        return (
            'BillAvenue indicates a complaint ticket may already exist for this transaction, or another rule prevents '
            'opening a new ticket. Use Complaint Tracking for this B-Connect transaction ID, or contact support with '
            'your transaction ID and the BillAvenue request ID shown on this screen.'
        )
    if (
        'complaint_register' in low
        and 'code=001' in low
        and ('unable to process' in low or 'unable to process your request' in low)
    ):
        return (
            'BillAvenue did not accept a complaint for this transaction reference. '
            'Double-check the CC… ID from your receipt, confirm the payment shows as successful under My Bills / transaction query, '
            'and retry after a few minutes if the payment was very recent. If this keeps happening, contact support with the transaction ID.'
        )
    if 'complaint_register' in low and 'code=205' in low:
        return (
            'BillAvenue returned error 205 for complaint registration (often access, institute rules, or request validation). '
            'Confirm disposition text matches BillAvenue’s official list, the B-Connect transaction ID is correct, and share the '
            'BillAvenue request ID from this screen with support if it continues.'
        )
    if 'cooling period' in low or 'cooling window' in low:
        return msg
    provider_msg = re.search(r'"errorMessage"\s*:\s*"([^"]+)"', msg)
    if provider_msg:
        clean = provider_msg.group(1).strip()
        if clean:
            return clean
    return msg


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
    payment_ui = get_biller_payment_ui_options(biller_id)
    master = get_biller_master(biller_id)
    plan_req = str(getattr(master, 'plan_mdm_requirement', '') or '').strip() if master else ''
    fetch_req = str(getattr(master, 'biller_fetch_requirement', '') or '').strip() if master else ''
    fetch_req_upper = fetch_req.upper().replace('-', '_').replace(' ', '_')
    quickpay_only = fetch_req_upper in (
        'NOT_SUPPORTED',
        'UNSUPPORTED',
        'QUICKPAY',
        'QUICKPAY_ONLY',
    ) or (
        'QUICKPAY' in fetch_req_upper
        and ('ONLY' in fetch_req_upper or 'NOT_SUPPORTED' in fetch_req_upper or 'UNSUPPORTED' in fetch_req_upper)
    )
    additional_info_schema = get_biller_additional_info_schema(biller_id)
    circle_q = str(request.query_params.get('circle') or request.query_params.get('Circle') or '').strip()
    plans_lite, plans_truncated = get_biller_plans_lite(biller_id, limit=100, circle=circle_q)
    input_guidance = None
    if schema and all(is_placeholder_style_param_name(str(r.get('param_name') or '')) for r in schema):
        input_guidance = (
            'This biller catalog uses internal BillAvenue test codes (parameter names like "a", "a b") instead of '
            'friendly labels. Enter the exact sample values from your BillAvenue / NPCI UAT document for this biller ID; '
            'random numbers usually fail fetch or return FNR003 from the biller switch.'
        )
    return Response(
        {
            'success': True,
            'data': {
                'biller_id': biller_id,
                'input_schema': schema,
                'input_guidance': input_guidance,
                'plan_mdm_requirement': plan_req,
                'biller_fetch_requirement': fetch_req,
                'quickpay_only': bool(quickpay_only),
                'additional_info_schema': additional_info_schema,
                'plans': plans_lite,
                'plans_truncated': plans_truncated,
                'payment_channels': payment_ui.get('payment_channels') or [],
                'payment_modes_by_channel': payment_ui.get('payment_modes_by_channel') or {},
                'payment_modes': payment_ui.get('payment_modes') or [],
                'payment_mode_channel_map': payment_ui.get('payment_mode_channel_map') or {},
                'default_payment_channel': payment_ui.get('default_channel') or '',
                'default_payment_mode': payment_ui.get('default_payment_mode') or 'Cash',
                'payment_options_source': payment_ui.get('source') or '',
            },
            'message': 'Biller schema retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def biller_plans_view(request, biller_id):
    """Partner: list cached plans for a biller (optional circle filter)."""
    circle_q = str(request.query_params.get('circle') or request.query_params.get('Circle') or '').strip()
    limit = 200
    try:
        limit = min(max(int(request.query_params.get('limit') or 200), 1), 500)
    except (TypeError, ValueError):
        limit = 200
    plans_lite, plans_truncated = get_biller_plans_lite(biller_id, limit=limit, circle=circle_q)
    master = get_biller_master(biller_id)
    return Response(
        {
            'success': True,
            'data': {
                'biller_id': biller_id,
                'plan_mdm_requirement': str(getattr(master, 'plan_mdm_requirement', '') or '').strip() if master else '',
                'circle': circle_q,
                'plans': plans_lite,
                'plans_truncated': plans_truncated,
                'plan_count': len(plans_lite),
            },
            'message': 'Plans retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def biller_plans_refresh_view(request, biller_id):
    """Partner: pull latest plans from BillAvenue for one plan-enabled biller."""
    bid = str(biller_id or '').strip()
    master = get_biller_master(bid)
    if not master:
        return Response(
            {'success': False, 'data': None, 'message': 'Biller not found in catalog.', 'errors': []},
            status=404,
        )
    req = str(getattr(master, 'plan_mdm_requirement', '') or '').strip().upper()
    if req not in ('OPTIONAL', 'MANDATORY', 'SUPPORTED', 'Y', 'YES', 'TRUE', '1'):
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'This biller does not use plan MDM.',
                'errors': [],
            },
            status=400,
        )
    try:
        out = pull_biller_plans(biller_ids=[bid])
        circle_q = str(
            (request.data or {}).get('circle')
            or request.query_params.get('circle')
            or ''
        ).strip()
        plans_lite, plans_truncated = get_biller_plans_lite(bid, limit=200, circle=circle_q)
        return Response(
            {
                'success': True,
                'data': {
                    'biller_id': bid,
                    'pull': out,
                    'plans': plans_lite,
                    'plans_truncated': plans_truncated,
                    'plan_count': len(plans_lite),
                },
                'message': 'Plans refreshed successfully',
                'errors': [],
            },
            status=200,
        )
    except BillAvenueClientError as e:
        msg = str(e or '')
        return Response(
            {
                'success': False,
                'data': None,
                'message': _friendly_plan_pull_error_message(msg),
                'errors': [],
            },
            status=400,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quote_view(request):
    assert_can_pay_out(request.user)
    assert_module_available(MODULE_BBPS)
    payload = request.data or {}
    amount = payload.get('amount')
    biller_id = str(payload.get('biller_id') or '').strip()
    bill_type = str(payload.get('bill_type') or '').strip()
    provider_id = payload.get('provider_id')
    if amount in (None, ''):
        return Response({'success': False, 'data': None, 'message': 'amount is required', 'errors': []}, status=400)
    if not biller_id:
        return Response({'success': False, 'data': None, 'message': 'biller_id is required', 'errors': []}, status=400)
    try:
        amount_dec = Decimal(str(amount))
        if amount_dec <= 0:
            raise ValueError('invalid amount')
        bill_data = {
            'biller_id': biller_id,
            'bill_type': bill_type,
            'provider_id': provider_id,
        }
        charge_info = resolve_commission_for_payment(amount=amount_dec, bill_data=bill_data)
        computed_charge = Decimal(
            str(charge_info.get('computed_charge') or charge_info.get('charge') or 0)
        )
        commission_impact = bool(getattr(settings, 'BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED', False))
        if commission_impact:
            applied_charge = Decimal(str(charge_info.get('charge') or 0))
            wallet_meta = {}
        else:
            wallet = resolve_bbps_wallet_service_charge(amount=amount_dec)
            applied_charge = wallet['charge']
            wallet_meta = {
                'wallet_service_charge_mode': wallet.get('mode'),
                'wallet_service_charge_flat': wallet.get('flat'),
                'wallet_service_charge_percent': wallet.get('percent'),
                'wallet_service_charge_source': wallet.get('source'),
            }
        total = amount_dec + applied_charge
        return Response(
            {
                'success': True,
                'data': {
                    'amount': float(amount_dec),
                    'computed_charge': float(computed_charge),
                    'applied_charge': float(applied_charge),
                    'total_deducted': float(total),
                    'shadow_mode': not commission_impact,
                    'commission_rule_code': charge_info.get('commission_rule_code') or '',
                    'commission_rule_snapshot': charge_info.get('commission_rule_snapshot') or {},
                    **wallet_meta,
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
                return bbps_error_response(
                    'biller_id is required for live BillAvenue bill fetch',
                    code='BBPS_FETCH_MISSING_BILLER',
                    retryable=False,
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
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

            derived_mobile = str(serializer.validated_data.get('mobile') or _extract_mobile_from_input_map(input_map) or '').strip()
            if not derived_mobile:
                derived_mobile = str(getattr(request.user, 'phone', '') or '').strip()
            derived_customer = str(serializer.validated_data.get('customer_number') or _extract_customer_number_from_input_map(input_map) or '').strip()
            plan_id = str(serializer.validated_data.get('plan_id') or '').strip()
            fetch_master = get_biller_master(biller_id)
            plan_req = str(getattr(fetch_master, 'plan_mdm_requirement', '') or '').strip().upper() if fetch_master else ''
            if plan_req == 'MANDATORY' and not plan_id:
                return bbps_error_response(
                    'Please select a plan before continuing.',
                    code='BBPS_PLAN_REQUIRED',
                    retryable=False,
                    errors=[{'param': 'plan_id', 'code': 'RPD053', 'message': 'Please select a plan before continuing.'}],
                    provider_code='RPD053',
                    action_hint='Load plans for this biller, select one, then validate again.',
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                wire_inputs = validate_biller_inputs(
                    biller_id=biller_id, input_map=input_map, plan_id=plan_id
                )
            except BbpsInputValidationError as ve:
                return bbps_error_response(
                    str(ve) or 'Invalid biller inputs',
                    code='BBPS_INPUT_INVALID',
                    retryable=False,
                    errors=list(getattr(ve, 'field_errors', []) or []),
                    provider_code='E135',
                    action_hint='Verify each required field matches what this biller expects.',
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            biller_adhoc_flag = bool(getattr(fetch_master, 'biller_adhoc', False)) if fetch_master else False
            flow = fetch_bill_with_cache(
                user=request.user,
                biller_id=biller_id,
                customer_info={'customerMobile': derived_mobile},
                input_params=wire_inputs,
                agent_device_info={
                    'initChannel': 'AGT',
                    'ip': request.META.get('REMOTE_ADDR') or '',
                },
                agent_id=_default_agent_id(),
                biller_adhoc=biller_adhoc_flag,
                plan_id=plan_id,
            )
            result = flow['bill_result']
            return Response({
                'success': True,
                'data': {
                    'bill': result,
                    'fetch_session_id': flow['fetch_session'].pk,
                    'normalized_inputs': {
                        'mobile': derived_mobile,
                        'customer_number': derived_customer,
                    },
                },
                'message': 'Bill fetched successfully',
                'errors': []
            }, status=status.HTTP_200_OK)
        except BillAvenueTransportError as e:
            info = resolve_bbps_error(str(e), endpoint='bill_fetch')
            is_timeout = info.retryable and info.provider_code == 'TIMEOUT'
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE if is_timeout else status.HTTP_400_BAD_REQUEST
            return bbps_error_response(
                info.user_message,
                code=info.app_code or ('BBPS_FETCH_TIMEOUT' if is_timeout else 'BBPS_FETCH_TRANSPORT'),
                retryable=bool(info.retryable),
                provider_code=info.provider_code or provider_code_from_exception(e),
                action_hint=info.action_hint,
                http_status=http_status,
            )
        except BillAvenueClientError as e:
            raw = str(e)
            info = resolve_bbps_error(raw, endpoint='bill_fetch')
            if info.provider_code == 'TIMEOUT' or 'timeout' in raw.lower() or 'timed out' in raw.lower():
                return bbps_error_response(
                    info.user_message,
                    code='BBPS_FETCH_TIMEOUT',
                    retryable=True,
                    provider_code=info.provider_code or provider_code_from_exception(e),
                    action_hint=info.action_hint,
                    http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            if info.app_code == 'BBPS_FETCH_QUICKPAY_ONLY' or info.provider_code == 'BRP046':
                return bbps_error_response(
                    info.user_message,
                    code='BBPS_FETCH_QUICKPAY_ONLY',
                    retryable=False,
                    provider_code=info.provider_code or provider_code_from_exception(e),
                    action_hint=info.action_hint,
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            return bbps_error_response(
                info.user_message,
                code=info.app_code or 'BBPS_FETCH_PROVIDER',
                retryable=bool(info.retryable),
                provider_code=info.provider_code or provider_code_from_exception(e),
                action_hint=info.action_hint,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        except TransactionFailed as e:
            info = resolve_bbps_error(str(e), endpoint='bill_fetch')
            return bbps_error_response(
                info.user_message,
                code=info.app_code or 'BBPS_FETCH_VALIDATION',
                retryable=bool(info.retryable),
                provider_code=info.provider_code,
                action_hint=info.action_hint,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            info = resolve_bbps_error(str(e), endpoint='bill_fetch')
            return bbps_error_response(
                info.user_message,
                code=info.app_code or 'BBPS_FETCH_FAILED',
                retryable=bool(info.retryable),
                provider_code=info.provider_code,
                action_hint=info.action_hint,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
    
    err = serializer.errors
    human = ''
    if isinstance(err, dict) and err:
        parts = []
        for k, v in err.items():
            if isinstance(v, list):
                parts.append(f'{k}: {", ".join(str(x) for x in v)}')
            else:
                parts.append(f'{k}: {v}')
        human = ' '.join(parts).strip()
    err_lines = []
    if isinstance(err, dict) and err:
        for k, v in err.items():
            if isinstance(v, list):
                err_lines.extend([f'{k}: {x}' for x in v])
            else:
                err_lines.append(f'{k}: {v}')
    return bbps_error_response(
        human or 'Failed to fetch bill',
        code='BBPS_FETCH_INVALID_REQUEST',
        retryable=False,
        errors=err_lines or ['Invalid request'],
        http_status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pay_bill_view(request):
    """
    Process bill payment.
    POST /api/bbps/pay/
    """
    assert_can_pay_out(request.user)
    assert_module_available(MODULE_BBPS)
    serializer = BillPaymentCreateSerializer(data=request.data)
    if serializer.is_valid():
        try:
            payload = dict(serializer.validated_data)
            mpin = str(payload.pop('mpin', '') or '').strip()
            if getattr(request.user, 'mpin_hash', None):
                if not mpin or not request.user.check_mpin(mpin):
                    return bbps_error_response(
                        'Invalid or missing MPIN.',
                        code='BBPS_PAY_INVALID_MPIN',
                        retryable=False,
                        http_status=status.HTTP_400_BAD_REQUEST,
                    )
            if payload.get('biller_id'):
                if payload.get('service_id') in (None, ''):
                    payload['service_id'] = f"PMBBPS{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
                if not payload.get('agent_id'):
                    payload['agent_id'] = _default_agent_id()
                ch = str(payload.get('init_channel') or 'AGT').strip() or 'AGT'
                adi = payload.get('agent_device_info') if isinstance(payload.get('agent_device_info'), dict) else {}
                if not adi or not str(adi.get('initChannel') or '').strip():
                    payload['agent_device_info'] = {
                        **(adi or {}),
                        'initChannel': ch,
                        'ip': str(request.META.get('REMOTE_ADDR') or adi.get('ip') or '').strip(),
                    }
                result = process_bill_payment_flow(user=request.user, bill_data=payload)
                bill_payment = result.get('bill_payment')
            else:
                return bbps_error_response(
                    'biller_id is required for live BillAvenue payment',
                    code='BBPS_PAY_MISSING_BILLER',
                    retryable=False,
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            response_data = BillPaymentSerializer(bill_payment).data if bill_payment else None
            return Response({
                'success': True,
                'data': {'bill_payment': response_data},
                'message': 'Bill payment processed successfully',
                'errors': []
            }, status=status.HTTP_201_CREATED)
        except InsufficientBalance as e:
            return bbps_error_response(
                _friendly_pay_error_message(str(e)) or 'Insufficient wallet balance for this payment.',
                code='BBPS_PAY_INSUFFICIENT_BALANCE',
                retryable=False,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        except BbpsProviderFloatInsufficient as e:
            return bbps_error_response(
                str(e) or 'Bill payment service is temporarily unavailable. Please try again shortly.',
                code='BBPS_PROVIDER_FLOAT_INSUFFICIENT',
                retryable=True,
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except BbpsInputValidationError as ve:
            return bbps_error_response(
                str(ve) or 'Invalid biller inputs',
                code='BBPS_INPUT_INVALID',
                retryable=False,
                errors=list(getattr(ve, 'field_errors', []) or []),
                provider_code='E135',
                action_hint='Verify each required field matches what this biller expects.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        except TransactionFailed as e:
            raw = str(e)
            info = resolve_bbps_error(raw, endpoint='bill_pay')
            if info.provider_code == 'TIMEOUT' or 'timeout' in raw.lower() or 'timed out' in raw.lower():
                return bbps_error_response(
                    info.user_message,
                    code='BBPS_PAY_TIMEOUT',
                    retryable=True,
                    provider_code=info.provider_code,
                    action_hint=info.action_hint,
                    http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            if info.provider_code == 'E204' or info.app_code == 'BBPS_PAY_REF_USED':
                return bbps_error_response(
                    info.user_message,
                    code='BBPS_PAY_REQUEST_ID_REUSED',
                    retryable=True,
                    provider_code=info.provider_code,
                    action_hint=info.action_hint,
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            if info.provider_code == 'E212' or info.app_code == 'BBPS_PAY_ADDITIONAL_INFO':
                return bbps_error_response(
                    info.user_message,
                    code='BBPS_PAY_ADDITIONAL_INFO_MISMATCH',
                    retryable=True,
                    provider_code=info.provider_code,
                    action_hint=info.action_hint,
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            return bbps_error_response(
                info.user_message,
                code=info.app_code or 'BBPS_PAY_DECLINED',
                retryable=bool(info.retryable),
                provider_code=info.provider_code,
                action_hint=info.action_hint,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception('pay-bill unexpected failure: %s', e)
            info = resolve_bbps_error(str(e), endpoint='bill_pay')
            return bbps_error_response(
                info.user_message,
                code=info.app_code or 'BBPS_PAY_FAILED',
                retryable=bool(info.retryable),
                provider_code=info.provider_code,
                action_hint=info.action_hint,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
    
    pay_err_lines = []
    if isinstance(serializer.errors, dict) and serializer.errors:
        for k, v in serializer.errors.items():
            if isinstance(v, list):
                pay_err_lines.extend([f'{k}: {x}' for x in v])
            else:
                pay_err_lines.append(f'{k}: {v}')
    return bbps_error_response(
        'Bill payment request could not be processed. Check all required fields.',
        code='BBPS_PAY_INVALID_REQUEST',
        retryable=False,
        errors=pay_err_lines or ['Invalid request'],
        http_status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bill_payments_list_view(request):
    """
    List bill payments (My Bills / Reports BBPS).
    GET /api/bbps/payments/

    Query: scope=self|team|platform (platform = Admin only), status, search, date_from, date_to,
    page, page_size (max 500).
    """
    from apps.bbps.bill_payments_filters import apply_bill_payments_list_filters
    from apps.bbps.bill_payments_scope import bill_payments_queryset_for_request
    from apps.transactions.reporting_scope import get_report_scope

    try:
        scope = get_report_scope(request)
        payments = apply_bill_payments_list_filters(bill_payments_queryset_for_request(request), request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        page_size = int(request.query_params.get('page_size', 20))
    except (TypeError, ValueError):
        page_size = 20
    page_size = max(1, min(page_size, 500))

    try:
        page = int(request.query_params.get('page', 1))
    except (TypeError, ValueError):
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid page parameter', 'errors': {'page': ['Must be an integer >= 1.']}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if page < 1:
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid page parameter', 'errors': {'page': ['Must be an integer >= 1.']}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    total = payments.count()
    start = (page - 1) * page_size
    paginated_payments = list(payments[start : start + page_size])
    serializer = BillPaymentSerializer(paginated_payments, many=True)
    from apps.bbps.bill_payment_balances import enrich_serialized_bill_payments

    payment_rows = enrich_serialized_bill_payments(paginated_payments, list(serializer.data))

    return Response(
        {
            'success': True,
            'data': {
                'payments': payment_rows,
                'total': total,
                'page': page,
                'page_size': page_size,
                'scope': scope,
            },
            'message': 'Bill payments retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bill_payments_export_csv_view(request):
    """
    Export bill payments CSV (same filters as list).
    GET /api/bbps/payments/export.csv
    """
    from apps.bbps.bill_payments_export import stream_bill_payments_csv
    from apps.bbps.bill_payments_filters import apply_bill_payments_list_filters
    from apps.bbps.bill_payments_scope import bill_payments_queryset_for_request

    try:
        payments = apply_bill_payments_list_filters(bill_payments_queryset_for_request(request), request)
    except PermissionDenied as e:
        return Response(
            {'success': False, 'data': None, 'message': str(e.detail if hasattr(e, 'detail') else e), 'errors': []},
            status=status.HTTP_403_FORBIDDEN,
        )
    return stream_bill_payments_csv('bbps_bill_payments', list(payments[:5000]))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bill_payment_detail_view(request, payment_id):
    """
    Get bill payment details.
    GET /api/bbps/payments/{id}/
    """
    from apps.bbps.bill_payments_scope import bill_payment_detail_queryset_for_request

    try:
        payment = bill_payment_detail_queryset_for_request(request).get(id=payment_id)
    except BillPayment.DoesNotExist:
        return Response(
            {'success': False, 'data': None, 'message': 'Bill payment not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    serializer = BillPaymentSerializer(payment)
    return Response(
        {
            'success': True,
            'data': {'payment': serializer.data},
            'message': 'Bill payment retrieved successfully',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def billavenue_config_view(request):
    """Load/save BillAvenue config by mode (uat|prod). One active live row."""
    mode_param = (
        request.query_params.get('mode')
        or request.data.get('mode')
        or ''
    )
    mode_param = str(mode_param or '').strip().lower()
    if mode_param not in ('uat', 'prod'):
        active = get_active_billavenue_config()
        if active:
            mode_param = normalize_billavenue_mode(active.mode)
        else:
            any_active = (
                BillAvenueConfig.objects.filter(is_deleted=False, is_active=True, mode__in=['uat', 'prod'])
                .order_by('-updated_at')
                .first()
            )
            mode_param = normalize_billavenue_mode(any_active.mode if any_active else 'uat')

    if request.method == 'GET':
        config = (
            BillAvenueConfig.objects.filter(mode=mode_param, is_deleted=False)
            .order_by('-is_active', '-updated_at')
            .first()
        )
        return Response(
            {
                'success': True,
                'data': {
                    'config': BillAvenueConfigSerializer(config).data if config else None,
                    'environments': environments_summary(),
                    'presets': MODE_PRESETS,
                    'live_mode': active_bbps_environment(),
                },
                'message': 'BillAvenue config retrieved successfully',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    data = dict(request.data or {})
    mode = normalize_billavenue_mode(data.get('mode') or mode_param)
    if str(data.get('mode') or '').lower() == 'mock' or mode not in ('uat', 'prod'):
        if str(data.get('mode') or '').lower() == 'mock':
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Mock mode is disabled. Use UAT or PROD mode.',
                    'errors': [],
                },
                status=400,
            )
    data['mode'] = mode
    data['name'] = MODE_PRESETS[mode]['name']
    if not str(data.get('base_url') or '').strip():
        data['base_url'] = MODE_PRESETS[mode]['base_url']

    config = get_or_create_billavenue_mode_row(mode)
    # Never allow POST to flip this row into the other environment.
    data['mode'] = mode
    data['name'] = MODE_PRESETS[mode]['name']

    make_active = bool(data.pop('make_active', False) or data.pop('activate', False))
    # is_active alone also activates when true
    want_active = make_active or bool(data.get('is_active'))

    ser = BillAvenueConfigSerializer(config, data=data, partial=True)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid config', 'errors': ser.errors}, status=400)
    cfg = ser.save()
    cfg.mode = mode
    cfg.name = MODE_PRESETS[mode]['name']
    cfg.save(update_fields=['mode', 'name', 'updated_at'])

    if want_active:
        missing = billavenue_credentials_missing(cfg)
        if missing:
            labels = {
                'working_key': 'Working Key',
                'iv': 'IV',
                'access_code': 'Access code',
                'institute_id': 'Institute ID',
                'base_url': 'Base URL',
            }
            pretty = ', '.join(labels.get(m, m) for m in missing)
            return Response(
                {
                    'success': False,
                    'data': {'missing_fields': missing, 'environments': environments_summary()},
                    'message': (
                        f'Cannot make {mode.upper()} live: {pretty} not saved. '
                        'Save credentials and Encrypted secrets for this environment first.'
                    ),
                    'errors': missing,
                },
                status=400,
            )
        activate_billavenue_config(cfg, user=request.user)
        cfg.refresh_from_db()
        _invalidate_bbps_user_catalog_cache()
    elif 'is_active' in data and not bool(data.get('is_active')):
        # Explicit deactivate of this row only — do not wipe secrets.
        if cfg.is_active:
            cfg.is_active = False
            cfg.save(update_fields=['is_active', 'updated_at'])

    # Ensure at least one active row when possible.
    if not BillAvenueConfig.objects.filter(is_deleted=False, is_active=True, mode__in=['uat', 'prod']).exists():
        activate_billavenue_config(cfg, user=request.user)
        cfg.refresh_from_db()

    return Response(
        {
            'success': True,
            'data': {
                'config': BillAvenueConfigSerializer(cfg).data,
                'environments': environments_summary(),
                'presets': MODE_PRESETS,
                'live_mode': active_bbps_environment(),
            },
            'message': 'BillAvenue config saved',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def billavenue_config_activate_view(request):
    """Switch partner live environment (UAT|PROD) without rewriting credentials."""
    mode = str(
        (request.data or {}).get('mode')
        or (request.data or {}).get('environment')
        or request.query_params.get('mode')
        or ''
    ).strip().lower()
    if mode not in ('uat', 'prod'):
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'mode must be uat or prod',
                'errors': ['mode'],
            },
            status=400,
        )
    cfg = get_or_create_billavenue_mode_row(mode)
    if not str(cfg.base_url or '').strip():
        cfg.base_url = MODE_PRESETS[mode]['base_url']
        cfg.save(update_fields=['base_url', 'updated_at'])
    missing = billavenue_credentials_missing(cfg)
    if missing:
        labels = {
            'working_key': 'Working Key',
            'working_key_invalid': 'Working Key (too short — paste full key from BillAvenue)',
            'iv': 'IV',
            'iv_invalid': 'IV (invalid — paste full IV from BillAvenue pack, not the label "IV")',
            'access_code': 'Access code',
            'institute_id': 'Institute ID',
            'base_url': 'Base URL',
        }
        pretty = ', '.join(labels.get(m, m) for m in missing)
        return Response(
            {
                'success': False,
                'data': {
                    'missing_fields': missing,
                    'environments': environments_summary(),
                },
                'message': (
                    f'Cannot switch to {mode.upper()}: {pretty} not saved for this environment. '
                    'Open BillAvenue Settings, select this environment, save credentials and Encrypted secrets, then retry.'
                ),
                'errors': missing,
            },
            status=400,
        )
    activate_billavenue_config(cfg, user=request.user)
    cfg.refresh_from_db()
    _invalidate_bbps_user_catalog_cache()
    return Response(
        {
            'success': True,
            'data': {
                'config': BillAvenueConfigSerializer(cfg).data,
                'environments': environments_summary(),
                'presets': MODE_PRESETS,
                'live_mode': active_bbps_environment(),
            },
            'message': f'{mode.upper()} is now live for partners',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def billavenue_config_secrets_view(request):
    mode = str(request.data.get('mode') or request.query_params.get('mode') or '').strip().lower()
    config_id = request.data.get('config_id') or request.data.get('config')
    config = None
    if config_id:
        config = BillAvenueConfig.objects.filter(pk=config_id, is_deleted=False).first()
    if config is None and mode in ('uat', 'prod'):
        config = get_or_create_billavenue_mode_row(mode)
    if config is None:
        config = get_active_billavenue_config() or BillAvenueConfig.objects.filter(is_deleted=False).order_by(
            '-is_active', '-updated_at'
        ).first()
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
            'data': {
                'config': BillAvenueConfigSerializer(config).data,
                'environments': environments_summary(),
                'live_mode': active_bbps_environment(),
            },
            'message': 'BillAvenue secrets updated',
            'errors': [],
        },
        status=200,
    )


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def billavenue_agent_profiles_view(request):
    if request.method == 'GET':
        cfg_id = request.query_params.get('config') or request.query_params.get('config_id')
        qs = BillAvenueAgentProfile.objects.filter(is_deleted=False)
        if cfg_id:
            qs = qs.filter(config_id=cfg_id)
        else:
            active = get_active_billavenue_config()
            if active:
                qs = qs.filter(config_id=active.pk)
        rows = qs.order_by('-created_at')
        return Response(
            {
                'success': True,
                'data': {'profiles': BillAvenueAgentProfileSerializer(rows, many=True).data},
                'message': 'Agent profiles retrieved successfully',
                'errors': [],
            },
            status=200,
        )
    if request.method == 'DELETE':
        req_id = request.query_params.get('id') or (request.data or {}).get('id')
        obj = BillAvenueAgentProfile.objects.filter(pk=req_id, is_deleted=False).first() if req_id else None
        if not obj:
            return Response({'success': False, 'data': None, 'message': 'Agent profile not found', 'errors': []}, status=404)
        now = timezone.now()
        obj.is_deleted = True
        obj.deleted_at = now
        obj.enabled = False
        obj.save(update_fields=['is_deleted', 'deleted_at', 'enabled', 'updated_at'])
        return Response({'success': True, 'data': {'id': obj.pk}, 'message': 'Agent profile removed', 'errors': []}, status=200)
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


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_payment_mapping_view(request, biller_id: str):
    from apps.bbps.service_flow.compliance import bbps_channel_accepts_payment_mode
    from apps.bbps.service_flow.provider_policy import provider_policy_decision_for_combo

    bid = str(biller_id or '').strip()
    master = get_biller_master(bid)
    if not master:
        return Response({'success': False, 'data': None, 'message': 'Biller not found', 'errors': []}, status=404)
    cfg = get_active_billavenue_config()
    if not cfg:
        return Response({'success': False, 'data': None, 'message': 'Active BillAvenue config not found', 'errors': []}, status=400)

    channels = [
        str(x.payment_channel or '').strip().upper()
        for x in BbpsBillerPaymentChannelLimit.objects.filter(is_deleted=False, is_active=True, biller=master)
        if str(x.payment_channel or '').strip()
    ]
    channel_codes = sorted(list({c for c in channels if c}))
    modes = [
        str(x.payment_mode or '').strip()
        for x in BbpsBillerPaymentModeLimit.objects.filter(is_deleted=False, is_active=True, biller=master)
        if str(x.payment_mode or '').strip()
    ]
    mode_labels = sorted(list({m for m in modes if m}), key=lambda v: v.lower())

    matrix = []
    for ch in channel_codes:
        for mode in mode_labels:
            rule_valid = bool(bbps_channel_accepts_payment_mode(ch, mode))
            decision = provider_policy_decision_for_combo(
                biller_id=master.biller_id,
                biller_category=master.biller_category,
                payment_mode=mode,
                payment_channel=ch,
            )
            matrix.append(
                {
                    'payment_channel': ch,
                    'payment_mode': mode,
                    'bbps_rule_valid': rule_valid,
                    'policy_action': 'allow' if decision is True else ('deny' if decision is False else 'inherit'),
                }
            )

    if request.method == 'GET':
        rows = BillAvenueModeChannelPolicy.objects.filter(
            is_deleted=False,
            enabled=True,
            config=cfg,
            biller_id=master.biller_id,
        ).order_by('payment_channel', 'payment_mode', '-created_at')
        return Response(
            {
                'success': True,
                'data': {
                    'biller_id': master.biller_id,
                    'biller_name': master.biller_name,
                    'biller_category': master.biller_category,
                    'mdm_channels': channel_codes,
                    'mdm_modes': mode_labels,
                    'matrix': matrix,
                    'policies': BillAvenueModeChannelPolicySerializer(rows, many=True).data,
                },
                'message': 'Biller payment mapping retrieved',
                'errors': [],
            },
            status=200,
        )

    allowed_channels = [
        str(c or '').strip().upper()
        for c in (request.data.get('allowed_channels') or [])
        if str(c or '').strip()
    ]
    allowed_set = set(allowed_channels)
    if not allowed_set:
        return Response({'success': False, 'data': None, 'message': 'allowed_channels is required', 'errors': []}, status=400)

    now = timezone.now()
    BillAvenueModeChannelPolicy.objects.filter(
        is_deleted=False,
        config=cfg,
        biller_id=master.biller_id,
    ).update(is_deleted=True, deleted_at=now, enabled=False)

    created = 0
    for row in matrix:
        if not row['bbps_rule_valid']:
            continue
        action = 'allow' if row['payment_channel'] in allowed_set else 'deny'
        BillAvenueModeChannelPolicy.objects.create(
            config=cfg,
            payment_mode=row['payment_mode'],
            payment_channel=row['payment_channel'],
            action=action,
            biller_id=master.biller_id,
            biller_category='',
            enabled=True,
        )
        created += 1

    return Response(
        {
            'success': True,
            'data': {
                'biller_id': master.biller_id,
                'saved_allowed_channels': sorted(list(allowed_set)),
                'rules_written': created,
            },
            'message': 'Biller payment mapping saved',
            'errors': [],
        },
        status=200,
    )


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


def _invalidate_provider_cache(*category_codes: str, environment: str | None = None):
    env = catalog_cache_env_key(environment)
    for code in category_codes:
        if code:
            cache.delete(f"bbps:providers:{env}:{normalize_category_code(code)}")
            # Legacy key (pre-env) — clear to avoid stale partner browse.
            cache.delete(f"bbps:providers:{normalize_category_code(code)}")


def _invalidate_bbps_user_catalog_cache():
    category_codes = set()
    category_codes.update(
        str(code or '').strip()
        for code in BbpsServiceCategory.objects.filter(is_deleted=False).values_list('code', flat=True)
    )
    category_codes.update(
        str(code or '').strip()
        for code in biller_master_qs_for_env().values_list('biller_category', flat=True)
    )
    _invalidate_provider_cache(*[c for c in category_codes if c])


def _extract_mobile_from_input_map(input_map: dict) -> str:
    for key, value in (input_map or {}).items():
        k = str(key or '').strip().lower().replace('_', ' ').replace('-', ' ')
        if ('mobile' in k or 'phone' in k) and str(value or '').strip():
            return str(value).strip()
    return ''


def _extract_customer_number_from_input_map(input_map: dict) -> str:
    for key, value in (input_map or {}).items():
        k = str(key or '').strip().lower().replace('_', ' ').replace('-', ' ')
        if ('customer' in k and ('id' in k or 'number' in k or 'no' in k)) and str(value or '').strip():
            return str(value).strip()
    return ''


def _error_payload(*, code: str, message: str, hint: str = '', errors=None) -> dict:
    """Standardized API error payload for admin BBPS operations."""
    trace_id = uuid.uuid4().hex
    out = {
        'success': False,
        'data': {
            'code': code,
            'actionable_hint': hint,
            'trace_id': trace_id,
        },
        'message': message,
        'errors': errors or [],
    }
    return out


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def integration_health_view(request):
    cfg = get_active_billavenue_config()
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
    stale_billers = biller_master_qs_for_env().filter(is_stale=True).count()
    unmapped_billers = biller_master_qs_for_env().exclude(
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
            payload: dict = {}
            if probe_agent:
                payload['agentId'] = str(probe_agent.agent_id or '').strip()
            # Agent-only biller_info often returns code=001; reuse latest cached biller so the probe matches sync MDM.
            cached_biller = (
                biller_master_qs_for_env()
                .exclude(biller_id='')
                .order_by('-updated_at', '-id')
                .values_list('biller_id', flat=True)
                .first()
            )
            if cached_biller:
                payload['billerId'] = str(cached_biller).strip()

            if not payload.get('agentId'):
                probe_ok = None
                probe_message = 'Skipped live MDM probe: no enabled agent profile with agent ID.'
            elif not payload.get('billerId'):
                probe_ok = None
                probe_message = (
                    'Skipped live MDM probe: no cached biller yet. Run Biller Sync once; agent-only biller_info '
                    'often returns code 001 from BillAvenue.'
                )
            else:
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
    stale_billers = biller_master_qs_for_env().filter(is_stale=True).count()
    unmapped_billers = biller_master_qs_for_env().exclude(
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


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def bbps_ops_observability_view(request):
    """Enterprise ops telemetry for BBPS flows and admin publish actions."""
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response(
            _error_payload(
                code='BBPS_GOVERNANCE_DISABLED',
                message='Provider governance is disabled',
                hint='Enable BBPS_PROVIDER_GOVERNANCE_ENABLED to use BBPS ops observability.',
            ),
            status=503,
        )
    recent = list(BbpsApiAuditLog.objects.filter(is_deleted=False).order_by('-created_at')[:300])
    endpoint_counts = {}
    failures = []
    for row in recent:
        key = str(row.endpoint_name or 'unknown')
        bucket = endpoint_counts.setdefault(key, {'total': 0, 'failed': 0})
        bucket['total'] += 1
        if not row.success:
            bucket['failed'] += 1
            failures.append(
                {
                    'endpoint_name': key,
                    'status_code': str(row.status_code or ''),
                    'error_message': str(row.error_message or ''),
                    'request_id': str(row.request_id or ''),
                    'created_at': row.created_at,
                }
            )
    awaited_count = BbpsPaymentAttempt.objects.filter(is_deleted=False, status='AWAITED').count()
    complaint_pending = BbpsComplaint.objects.filter(is_deleted=False).exclude(complaint_status__iexact='resolved').count()
    return Response(
        {
            'success': True,
            'data': {
                'endpoint_counts': endpoint_counts,
                'awaited_count': awaited_count,
                'complaint_pending_count': complaint_pending,
                'recent_failures': failures[:50],
            },
            'message': 'BBPS ops observability retrieved successfully',
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


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_master_admin_view(request):
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response({'success': False, 'data': None, 'message': 'Provider governance is disabled', 'errors': []}, status=503)
    live_mode = active_bbps_environment()
    if request.method == 'GET':
        env_param = str(request.query_params.get('environment') or request.query_params.get('mode') or '').strip().lower()
        catalog_env = normalize_billavenue_mode(env_param) if env_param in ('uat', 'prod') else live_mode
        category = request.query_params.get('category')
        q = str(request.query_params.get('q') or '').strip()
        active = str(request.query_params.get('active') or '').strip().lower()
        try:
            page = max(1, int(request.query_params.get('page') or 1))
        except (TypeError, ValueError):
            page = 1
        try:
            # Admin directory may request "All" (up to 50k) for bulk select/sync.
            page_size = max(1, min(50000, int(request.query_params.get('page_size') or 25)))
        except (TypeError, ValueError):
            page_size = 25
        qs = biller_master_qs_for_env(catalog_env).filter(soft_deleted_at__isnull=True).order_by('biller_name')
        if category:
            qs = qs.filter(biller_category__icontains=category)
        if q:
            qs = qs.filter(Q(biller_name__icontains=q) | Q(biller_id__icontains=q))
        if active in ('true', 'false'):
            qs = qs.filter(is_active_local=(active == 'true'))
        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        rows = qs[start:end]
        counts = catalog_counts_by_environment()
        return Response(
            {
                'success': True,
                'data': {
                    'billers': BbpsBillerMasterLiteSerializer(rows, many=True).data,
                    'live_mode': live_mode,
                    'catalog_environment': catalog_env,
                    'catalog_counts': counts,
                    'quota': _sync_quota_snapshot(),
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': (total + page_size - 1) // page_size if page_size else 1,
                    },
                },
                'message': 'Biller master retrieved successfully',
                'errors': [],
            },
            status=200,
        )
    # Manual create always lands in the live env (credentials/catalog alignment).
    ser = BbpsBillerMasterAdminSerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid biller payload', 'errors': ser.errors}, status=400)
    row = ser.save(
        source_type='manual',
        is_active_local=True,
        environment=live_mode,
        updated_by_admin_at=timezone.now(),
        version=1,
    )
    bootstrap_default_biller_policy_if_missing(biller=row)
    auto_plan_pull = _maybe_auto_pull_plans_for_billers([row.biller_id])
    _invalidate_bbps_user_catalog_cache()
    return Response(
        {
            'success': True,
            'data': {
                'biller': BbpsBillerMasterAdminSerializer(row).data,
                'auto_plan_pull': auto_plan_pull,
                'live_mode': live_mode,
                'catalog_environment': live_mode,
            },
            'message': f'Biller created in {live_mode.upper()} catalog',
            'errors': [],
        },
        status=201,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_master_category_counts_view(request):
    """
    GET /api/bbps/admin/biller-master/category-counts/?environment=uat|prod
    Aggregate biller counts per category for the BBPS Console directory sidebar.
    """
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response({'success': False, 'data': None, 'message': 'Provider governance is disabled', 'errors': []}, status=503)
    live_mode = active_bbps_environment()
    env_param = str(request.query_params.get('environment') or request.query_params.get('mode') or '').strip().lower()
    catalog_env = normalize_billavenue_mode(env_param) if env_param in ('uat', 'prod') else live_mode

    qs = biller_master_qs_for_env(catalog_env).filter(soft_deleted_at__isnull=True)
    raw = (
        qs.values('biller_category')
        .annotate(
            total=Count('id'),
            visible=Count('id', filter=Q(is_active_local=True)),
        )
        .order_by('-total')
    )
    categories = []
    totals = {'total': 0, 'visible': 0, 'hidden': 0}
    for row in raw:
        name = str(row.get('biller_category') or '').strip() or 'Uncategorized'
        total = int(row.get('total') or 0)
        visible = int(row.get('visible') or 0)
        categories.append(
            {
                'category': name,
                'total': total,
                'visible': visible,
                'hidden': total - visible,
            }
        )
    for c in categories:
        totals['total'] += c['total']
        totals['visible'] += c['visible']
        totals['hidden'] += c['hidden']
    return Response(
        {
            'success': True,
            'data': {
                'live_mode': live_mode,
                'catalog_environment': catalog_env,
                'categories': categories,
                'totals': totals,
                'catalog_counts': catalog_counts_by_environment(),
            },
            'message': 'Biller category counts retrieved',
            'errors': [],
        },
        status=200,
    )


def _admin_delete_biller_rows(qs):
    """Mark biller master rows deleted for admin directory (same semantics as clear-all)."""
    now = timezone.now()
    count = qs.count()
    qs.update(
        is_deleted=True,
        deleted_at=now,
        soft_deleted_at=now,
        is_active_local=False,
        updated_by_admin_at=now,
        updated_at=now,
    )
    return count


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_master_admin_detail_view(request, pk: int):
    row = BbpsBillerMaster.objects.filter(pk=pk, is_deleted=False).first()
    if not row:
        return Response({'success': False, 'data': None, 'message': 'Biller not found', 'errors': []}, status=404)
    if request.method == 'DELETE':
        _admin_delete_biller_rows(BbpsBillerMaster.objects.filter(pk=row.pk))
        _invalidate_bbps_user_catalog_cache()
        return Response(
            {
                'success': True,
                'data': {'id': row.pk, 'biller_id': row.biller_id, 'environment': row.environment},
                'message': 'Biller deleted',
                'errors': [],
            },
            status=200,
        )
    ser = BbpsBillerMasterAdminSerializer(row, data=request.data, partial=True)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid biller update', 'errors': ser.errors}, status=400)
    updated = ser.save(
        updated_by_admin_at=timezone.now(),
        version=(row.version or 1) + 1,
    )
    auto_plan_pull = _maybe_auto_pull_plans_for_billers([updated.biller_id])
    _invalidate_bbps_user_catalog_cache()
    return Response({'success': True, 'data': {'biller': BbpsBillerMasterAdminSerializer(updated).data, 'auto_plan_pull': auto_plan_pull}, 'message': 'Biller updated', 'errors': []}, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_master_disable_view(request, pk: int):
    row = BbpsBillerMaster.objects.filter(pk=pk, is_deleted=False).first()
    if not row:
        return Response({'success': False, 'data': None, 'message': 'Biller not found', 'errors': []}, status=404)
    row.is_active_local = False
    row.updated_by_admin_at = timezone.now()
    row.save(update_fields=['is_active_local', 'updated_by_admin_at', 'updated_at'])
    _invalidate_bbps_user_catalog_cache()
    return Response({'success': True, 'data': {'id': row.pk, 'is_active_local': row.is_active_local}, 'message': 'Biller disabled', 'errors': []}, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_master_enable_view(request, pk: int):
    row = BbpsBillerMaster.objects.filter(pk=pk, is_deleted=False).first()
    if not row:
        return Response({'success': False, 'data': None, 'message': 'Biller not found', 'errors': []}, status=404)
    row.is_active_local = True
    if row.soft_deleted_at is not None:
        row.soft_deleted_at = None
    row.updated_by_admin_at = timezone.now()
    row.save(update_fields=['is_active_local', 'soft_deleted_at', 'updated_by_admin_at', 'updated_at'])
    _invalidate_bbps_user_catalog_cache()
    return Response({'success': True, 'data': {'id': row.pk, 'is_active_local': row.is_active_local}, 'message': 'Biller enabled', 'errors': []}, status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_master_admin_full_detail_view(request, pk: int):
    row = BbpsBillerMaster.objects.filter(pk=pk, is_deleted=False).first()
    if not row:
        return Response({'success': False, 'data': None, 'message': 'Biller not found', 'errors': []}, status=404)
    data = BbpsBillerMasterAdminSerializer(row).data
    data['input_params'] = list(
        BbpsBillerInputParam.objects.filter(is_deleted=False, biller=row).order_by('display_order', 'id').values(
            'param_name', 'data_type', 'is_optional', 'min_length', 'max_length', 'regex', 'visibility', 'default_values', 'display_order'
        )
    )
    data['payment_modes'] = list(
        BbpsBillerPaymentModeLimit.objects.filter(is_deleted=False, biller=row).order_by('payment_mode').values(
            'payment_mode', 'min_amount', 'max_amount', 'is_active'
        )
    )
    data['payment_channels'] = list(
        BbpsBillerPaymentChannelLimit.objects.filter(is_deleted=False, biller=row).order_by('payment_channel').values(
            'payment_channel', 'min_amount', 'max_amount', 'is_active'
        )
    )
    mode_names = [
        str(x.get('payment_mode') or '').strip()
        for x in data.get('payment_modes') or []
        if str(x.get('payment_mode') or '').strip()
    ]
    channel_names = [
        str(x.get('payment_channel') or '').strip().upper()
        for x in data.get('payment_channels') or []
        if str(x.get('payment_channel') or '').strip()
    ]
    channel_mode_matrix = []
    for ch in channel_names:
        accepted = display_payment_modes_for_channel(ch, mode_names if mode_names else None)
        channel_mode_matrix.append(
            {
                'payment_channel': ch,
                'accepted_payment_modes': accepted,
                'accepted_payment_modes_count': len(accepted),
            }
        )
    mode_channel_matrix = []
    for mode in mode_names:
        eligible_channels = [ch for ch in channel_names if bbps_channel_accepts_payment_mode(ch, mode)]
        mode_channel_matrix.append(
            {
                'payment_mode': mode,
                'eligible_payment_channels': eligible_channels,
                'eligible_payment_channels_count': len(eligible_channels),
            }
        )
    data['payment_acceptance_matrix'] = {
        'payment_channels_supported': channel_names,
        'payment_modes_supported': mode_names,
        'channel_to_modes': channel_mode_matrix,
        'mode_to_channels': mode_channel_matrix,
    }
    data['additional_info_schema'] = list(
        BbpsBillerAdditionalInfoSchema.objects.filter(is_deleted=False, biller=row).order_by('info_group', 'info_name').values(
            'info_group', 'info_name', 'data_type', 'is_optional'
        )
    )
    data['plans'] = list(
        BbpsBillerPlanMeta.objects.filter(is_deleted=False, biller=row).order_by('-updated_at').values(
            'plan_id', 'category_type', 'category_sub_type', 'amount_in_rupees', 'plan_desc', 'effective_from', 'effective_to', 'status', 'plan_additional_info'
        )[:200]
    )
    data['ccf1_configs'] = list(
        BbpsBillerCcf1Config.objects.filter(is_deleted=False, biller=row).values(
            'fee_code', 'fee_direction', 'flat_fee', 'percent_fee', 'fee_min_amount', 'fee_max_amount'
        )
    )
    return Response({'success': True, 'data': {'biller': data}, 'message': 'Biller details retrieved', 'errors': []}, status=200)


def _raw_payload_fingerprint(raw) -> tuple[str, int]:
    if not isinstance(raw, dict):
        raw = {}
    try:
        blob = json.dumps(raw, sort_keys=True, default=str).encode('utf-8')
        return hashlib.sha256(blob).hexdigest(), len(blob)
    except Exception:
        return '', 0


def _suggest_plan_pull_from_master(master: BbpsBillerMaster) -> bool:
    plan_req = str(getattr(master, 'plan_mdm_requirement', '') or '').strip().upper()
    if not plan_req:
        return False
    return (
        'MANDATORY' in plan_req
        or 'OPTIONAL' in plan_req
        or plan_req in ('Y', 'YES', 'TRUE', '1')
    )


def _maybe_auto_pull_plans_for_billers(biller_ids: list[str]) -> dict:
    out = {'attempted': False, 'eligible_ids': [], 'plan_count': 0, 'error': ''}
    if not bool(getattr(settings, 'BBPS_AUTO_PULL_PLANS_ON_SYNC', True)):
        return out
    cleaned = [str(x or '').strip() for x in (biller_ids or []) if str(x or '').strip()]
    if not cleaned:
        return out
    cap = int(getattr(settings, 'BBPS_AUTO_PULL_PLANS_MAX_BILLERS', 50) or 50)
    cap = max(1, cap)
    masters = {
        m.biller_id: m
        for m in biller_master_qs_for_env().filter(biller_id__in=cleaned)
    }
    eligible = [bid for bid in cleaned if masters.get(bid) and _suggest_plan_pull_from_master(masters[bid])][:cap]
    if not eligible:
        return out
    out['attempted'] = True
    out['eligible_ids'] = eligible
    try:
        pulled = pull_biller_plans(biller_ids=eligible)
        out['plan_count'] = int(pulled.get('plan_count') or 0)
    except Exception as exc:
        out['error'] = str(exc or '')
    return out


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_catalog_summary_view(request, biller_id: str):
    bid = str(biller_id or '').strip()
    master = get_biller_master(bid)
    if not master:
        return Response({'success': False, 'data': None, 'message': 'Biller not found', 'errors': []}, status=404)
    params_count = BbpsBillerInputParam.objects.filter(is_deleted=False, biller=master).count()
    modes_count = BbpsBillerPaymentModeLimit.objects.filter(is_deleted=False, biller=master).count()
    channels_count = BbpsBillerPaymentChannelLimit.objects.filter(is_deleted=False, biller=master).count()
    addl_count = BbpsBillerAdditionalInfoSchema.objects.filter(is_deleted=False, biller=master).count()
    plans_count = BbpsBillerPlanMeta.objects.filter(is_deleted=False, biller=master).count()
    raw_for_fp = master.raw_payload if isinstance(master.raw_payload, dict) else {}
    fp, sz = _raw_payload_fingerprint(raw_for_fp)
    input_schema = get_biller_input_schema(bid)
    payment_ui = get_biller_payment_ui_options(bid)
    additional_info_schema = get_biller_additional_info_schema(bid)
    plans_lite, plans_truncated = get_biller_plans_lite(bid, limit=50)
    latest_plan_run = (
        BbpsPlanPullRun.objects.filter(is_deleted=False, requested_biller_ids__contains=[bid])
        .order_by('-created_at')
        .first()
    )
    latest_plan_pull = None
    if latest_plan_run:
        latest_plan_pull = {
            'run_id': latest_plan_run.pk,
            'created_at': latest_plan_run.created_at.isoformat() if latest_plan_run.created_at else None,
            'response_code': latest_plan_run.response_code,
            'plan_count': latest_plan_run.plan_count,
            'error_message': latest_plan_run.error_message,
        }
    plan_req = str(getattr(master, 'plan_mdm_requirement', '') or '').strip()
    data = {
        'master': {
            'biller_id': master.biller_id,
            'biller_name': master.biller_name,
            'biller_category': master.biller_category,
            'biller_status': master.biller_status,
            'plan_mdm_requirement': plan_req,
            'biller_fetch_requirement': getattr(master, 'biller_fetch_requirement', ''),
            'is_active_local': master.is_active_local,
            'is_stale': getattr(master, 'is_stale', False),
            'last_synced_at': master.last_synced_at.isoformat() if getattr(master, 'last_synced_at', None) else None,
            'last_sync_status': getattr(master, 'last_sync_status', ''),
            'last_sync_request_id': getattr(master, 'last_sync_request_id', ''),
            'last_sync_error': getattr(master, 'last_sync_error', ''),
            'source_type': getattr(master, 'source_type', ''),
        },
        'counts': {
            'input_params': params_count,
            'payment_modes': modes_count,
            'payment_channels': channels_count,
            'additional_info_schema_rows': addl_count,
            'plan_meta_rows': plans_count,
        },
        'raw_payload_fingerprint_sha256': fp,
        'raw_payload_size_bytes': sz,
        'suggest_plan_pull': _suggest_plan_pull_from_master(master),
        'latest_plan_pull': latest_plan_pull,
        'pay_ui_projection': {
            'input_schema': input_schema,
            'payment_channels': payment_ui.get('payment_channels') or [],
            'payment_modes': payment_ui.get('payment_modes') or [],
            'payment_mode_channel_map': payment_ui.get('payment_mode_channel_map') or {},
            'payment_modes_by_channel': payment_ui.get('payment_modes_by_channel') or {},
            'default_payment_channel': payment_ui.get('default_channel') or '',
            'default_payment_mode': payment_ui.get('default_payment_mode') or '',
            'payment_options_source': payment_ui.get('source') or '',
            'additional_info_schema': additional_info_schema,
            'plans_lite': plans_lite,
            'plans_truncated': plans_truncated,
        },
    }
    return Response({'success': True, 'data': data, 'message': 'Catalog summary retrieved', 'errors': []}, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_master_admin_clear_all_view(request):
    live_mode = active_bbps_environment()
    env_param = str(
        (request.data or {}).get('environment')
        or request.query_params.get('environment')
        or live_mode
    ).strip().lower()
    env = normalize_billavenue_mode(env_param) if env_param in ('uat', 'prod') else live_mode
    qs = biller_master_qs_for_env(env)
    count = _admin_delete_biller_rows(qs)
    _invalidate_bbps_user_catalog_cache()
    return Response(
        {
            'success': True,
            'data': {
                'cleared_count': count,
                'environment': env,
                'live_mode': live_mode,
                'catalog_counts': catalog_counts_by_environment(),
            },
            'message': f'All {env.upper()} billers removed from that catalog (other environment preserved)',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_master_admin_bulk_delete_view(request):
    """Delete selected billers from one catalog environment (UAT or PROD)."""
    live_mode = active_bbps_environment()
    data = request.data or {}
    env_param = str(data.get('environment') or data.get('mode') or live_mode).strip().lower()
    env = normalize_billavenue_mode(env_param) if env_param in ('uat', 'prod') else live_mode

    raw_ids = data.get('biller_ids')
    if raw_ids is None:
        raw_ids = data.get('ids') or []
    if isinstance(raw_ids, str):
        raw_ids = [x.strip() for x in re.split(r'[\s,\n]+', raw_ids) if x.strip()]
    if not isinstance(raw_ids, (list, tuple)):
        return Response(
            {'success': False, 'data': None, 'message': 'biller_ids must be a list', 'errors': ['biller_ids']},
            status=400,
        )
    biller_ids = [str(x or '').strip() for x in raw_ids if str(x or '').strip()]
    biller_ids = list(dict.fromkeys(biller_ids))
    if not biller_ids:
        return Response(
            {'success': False, 'data': None, 'message': 'Select at least one biller to delete', 'errors': ['biller_ids']},
            status=400,
        )
    if len(biller_ids) > 2000:
        return Response(
            {'success': False, 'data': None, 'message': 'Maximum 2000 billers per delete', 'errors': []},
            status=400,
        )

    qs = biller_master_qs_for_env(env).filter(soft_deleted_at__isnull=True, biller_id__in=biller_ids)
    deleted_ids = list(qs.values_list('biller_id', flat=True))
    count = _admin_delete_biller_rows(qs)
    _invalidate_bbps_user_catalog_cache()
    return Response(
        {
            'success': True,
            'data': {
                'deleted_count': count,
                'biller_ids': deleted_ids,
                'environment': env,
                'live_mode': live_mode,
                'catalog_counts': catalog_counts_by_environment(),
            },
            'message': f'Deleted {count} {env.upper()} biller(s)',
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
    action = str(request.data.get('action') or '').strip().lower()
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


def _mdm_catalog_serialize_map(row: BbpsProviderBillerMap) -> dict:
    data = BbpsProviderBillerMapSerializer(row).data
    data['blocked_by'] = governance_block_reasons_for_map(row)
    data['approval_status'] = _approval_status(row)
    return data


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def mdm_catalog_summary_view(request):
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response(
            _error_payload(
                code='BBPS_GOVERNANCE_DISABLED',
                message='Provider governance is disabled',
                hint='Enable BBPS_PROVIDER_GOVERNANCE_ENABLED to use catalog controls.',
            ),
            status=503,
        )
    rows = list(
        BbpsProviderBillerMap.objects.filter(is_deleted=False)
        .select_related('provider__category', 'biller_master')
        .order_by('-updated_at')[:2000]
    )
    total = len(rows)
    auto_synced = [r for r in rows if bool((r.metadata or {}).get('auto_synced'))]
    published = 0
    blocked = 0
    draft = 0
    blocker_counts = {}
    for row in auto_synced:
        reasons = governance_block_reasons_for_map(row)
        if reasons:
            blocked += 1
            for reason in reasons:
                blocker_counts[reason] = blocker_counts.get(reason, 0) + 1
        elif row.is_active:
            published += 1
        else:
            draft += 1
    return Response(
        {
            'success': True,
            'data': {
                'total_maps': total,
                'auto_synced_maps': len(auto_synced),
                'published_maps': published,
                'blocked_maps': blocked,
                'draft_maps': draft,
                'blocker_counts': blocker_counts,
            },
            'message': 'MDM catalog summary retrieved successfully',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def mdm_catalog_bulk_publish_view(request):
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response(
            _error_payload(
                code='BBPS_GOVERNANCE_DISABLED',
                message='Provider governance is disabled',
                hint='Enable BBPS_PROVIDER_GOVERNANCE_ENABLED to use catalog controls.',
            ),
            status=503,
        )
    ids = request.data.get('map_ids') or []
    published = bool(request.data.get('published'))
    if not isinstance(ids, list) or not ids:
        return Response(
            _error_payload(
                code='BBPS_INVALID_REQUEST',
                message='map_ids is required',
                hint='Pass map_ids as a non-empty list of map IDs.',
            ),
            status=400,
        )
    rows = list(
        BbpsProviderBillerMap.objects.filter(is_deleted=False, id__in=ids)
        .select_related('provider__category', 'biller_master')
    )
    found_ids = {r.id for r in rows}
    missing = [i for i in ids if i not in found_ids]
    changed = 0
    unchanged = 0
    blocked = []
    with transaction.atomic():
        for row in rows:
            cat = row.provider.category
            if published:
                cat.is_active = True
                cat.save(update_fields=['is_active', 'updated_at'])
                if not BbpsCategoryCommissionRule.objects.filter(
                    is_deleted=False,
                    is_active=True,
                    category=cat,
                ).exists():
                    rule = BbpsCategoryCommissionRule.objects.create(
                        category=cat,
                        rule_code='mdm-catalog-default',
                        commission_type='flat',
                        value=Decimal('0'),
                        min_commission=Decimal('0'),
                        max_commission=Decimal('0'),
                        is_active=True,
                        notes='Auto-created for MDM catalog publish (bulk).',
                    )
                    BbpsCommissionAudit.objects.create(
                        rule=rule,
                        changed_by_user_id=request.user.pk if request.user and request.user.is_authenticated else None,
                        action='create',
                        previous_snapshot={},
                        new_snapshot=_as_audit_snapshot(rule),
                        reason='mdm_catalog_bulk_publish',
                    )
                if not row.provider.is_active:
                    row.provider.is_active = True
                    _set_approval_status(row.provider, 'approved')
                    row.provider.save(update_fields=['is_active', 'metadata', 'updated_at'])
                if row.is_active:
                    unchanged += 1
                else:
                    row.is_active = True
                    _set_approval_status(row, 'approved')
                    row.save(update_fields=['is_active', 'metadata', 'updated_at'])
                    changed += 1
                reasons = governance_block_reasons_for_map(row)
                if reasons:
                    blocked.append({'id': row.id, 'blocked_by': reasons})
            else:
                if row.is_active:
                    row.is_active = False
                    _set_approval_status(row, 'pending')
                    row.save(update_fields=['is_active', 'metadata', 'updated_at'])
                    changed += 1
                else:
                    unchanged += 1
            _invalidate_provider_cache(cat.code)
    BbpsApiAuditLog.objects.create(
        endpoint_name='mdm_catalog_bulk_publish',
        request_id='',
        service_id='',
        status_code='200',
        latency_ms=0,
        success=True,
        request_meta={'map_ids': ids, 'published': published},
        response_meta={
            'changed': changed,
            'unchanged': unchanged,
            'blocked': len(blocked),
            'missing': len(missing),
        },
        error_message='',
    )
    return Response(
        {
            'success': True,
            'data': {
                'changed_count': changed,
                'unchanged_count': unchanged,
                'blocked': blocked,
                'missing_ids': missing,
            },
            'message': 'Bulk publish completed' if published else 'Bulk unpublish completed',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def mdm_catalog_publish_view(request):
    """
    One-step publish for MDM-synced maps: activate category, ensure commission rule,
    activate provider and map. Unpublish only deactivates the map (other maps may share category).
    """
    if not getattr(settings, 'BBPS_PROVIDER_GOVERNANCE_ENABLED', True):
        return Response(
            _error_payload(
                code='BBPS_GOVERNANCE_DISABLED',
                message='Provider governance is disabled',
                hint='Enable BBPS_PROVIDER_GOVERNANCE_ENABLED to use catalog controls.',
            ),
            status=503,
        )
    ser = MdmCatalogPublishSerializer(data=request.data or {})
    if not ser.is_valid():
        return Response(
            _error_payload(
                code='BBPS_INVALID_REQUEST',
                message='Invalid request',
                hint='Provide valid map_id and published boolean.',
                errors=ser.errors,
            ),
            status=400,
        )
    map_id = ser.validated_data['map_id']
    published = ser.validated_data['published']
    row = (
        BbpsProviderBillerMap.objects.filter(pk=map_id, is_deleted=False)
        .select_related('provider__category', 'biller_master')
        .first()
    )
    if not row:
        return Response(
            _error_payload(
                code='BBPS_MAP_NOT_FOUND',
                message='Map not found',
                hint='Refresh the catalog and retry with an existing map.',
            ),
            status=404,
        )

    cat_code = ''
    if row.provider and row.provider.category:
        cat_code = row.provider.category.code or ''

    if not published:
        with transaction.atomic():
            row.is_active = False
            _set_approval_status(row, 'pending')
            row.save(update_fields=['is_active', 'metadata', 'updated_at'])
        _invalidate_provider_cache(cat_code)
        row.refresh_from_db()
        return Response(
            {
                'success': True,
                'data': {
                    'map': _mdm_catalog_serialize_map(row),
                    'commission_rule_created': False,
                    'warnings': governance_block_reasons_for_map(row),
                },
                'message': 'Service hidden from end users (map deactivated)',
                'errors': [],
            },
            status=200,
        )

    commission_rule_created = False
    with transaction.atomic():
        cat = row.provider.category
        cat.is_active = True
        cat.save(update_fields=['is_active', 'updated_at'])

        has_rule = BbpsCategoryCommissionRule.objects.filter(
            is_deleted=False,
            is_active=True,
            category=cat,
        ).exists()
        if not has_rule:
            rule = BbpsCategoryCommissionRule.objects.create(
                category=cat,
                rule_code='mdm-catalog-default',
                commission_type='flat',
                value=Decimal('0'),
                min_commission=Decimal('0'),
                max_commission=Decimal('0'),
                is_active=True,
                notes='Auto-created for MDM catalog publish (edit under Commission Rules).',
            )
            BbpsCommissionAudit.objects.create(
                rule=rule,
                changed_by_user_id=request.user.pk if request.user and request.user.is_authenticated else None,
                action='create',
                previous_snapshot={},
                new_snapshot=_as_audit_snapshot(rule),
                reason='mdm_catalog_publish',
            )
            commission_rule_created = True

        prov = row.provider
        prov.is_active = True
        _set_approval_status(prov, 'approved')
        prov.save(update_fields=['is_active', 'metadata', 'updated_at'])

        row.is_active = True
        _set_approval_status(row, 'approved')
        row.save(update_fields=['is_active', 'metadata', 'updated_at'])

    _invalidate_provider_cache(cat_code)
    row.refresh_from_db()
    row = (
        BbpsProviderBillerMap.objects.filter(pk=row.pk, is_deleted=False)
        .select_related('provider__category', 'biller_master')
        .first()
    )
    warnings = governance_block_reasons_for_map(row)
    BbpsApiAuditLog.objects.create(
        endpoint_name='mdm_catalog_publish',
        request_id='',
        service_id='',
        status_code='200',
        latency_ms=0,
        success=True,
        request_meta={'map_id': map_id, 'published': published},
        response_meta={'warnings': warnings, 'commission_rule_created': commission_rule_created},
        error_message='',
    )
    return Response(
        {
            'success': True,
            'data': {
                'map': _mdm_catalog_serialize_map(row),
                'commission_rule_created': commission_rule_created,
                'warnings': warnings,
            },
            'message': 'Service published to end users' if not warnings else 'Published with remaining checks — see warnings',
            'errors': [],
        },
        status=200,
    )


def _sync_quota_snapshot(environment: str | None = None):
    return sync_quota_snapshot(environment)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def sync_billers_view(request):
    payload = dict(request.data or {})
    raw_ids = payload.get('biller_ids')
    if isinstance(raw_ids, str):
        payload['biller_ids'] = [str(x or '').strip() for x in re.split(r'[\s,\n]+', raw_ids) if str(x or '').strip()]
    ser = BillerSyncRequestSerializer(data=payload)
    if not ser.is_valid():
        return Response(
            {
                'success': False,
                'data': {'actionable_hint': 'Use comma, space, or newline separated biller IDs (max 2000).'},
                'message': 'Invalid sync request',
                'errors': ser.errors,
            },
            status=400,
        )
    biller_ids = ser.validated_data.get('biller_ids') or []
    live_mode = active_bbps_environment()
    requested_env = str((request.data or {}).get('environment') or '').strip().lower()
    sync_env = normalize_billavenue_mode(requested_env) if requested_env in ('uat', 'prod') else live_mode
    try:
        out = run_mdm_sync_batch(
            biller_ids,
            environment=sync_env,
            user=request.user,
            invalidate_cache=_invalidate_bbps_user_catalog_cache,
        )
        return Response(
            {'success': True, 'data': out, 'message': f'{sync_env.upper()} biller sync completed', 'errors': []},
            status=200,
        )
    except MdmSyncQuotaExhausted as e:
        return Response(
            {
                'success': False,
                'data': e.quota or sync_quota_snapshot(sync_env),
                'message': str(e),
                'errors': [],
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    except MdmSyncBatchError as e:
        live = active_bbps_environment()
        code = e.code
        data = dict(e.data or {})
        if code in ('001', '205', 'PARSE', '202'):
            msg_l = str(e or '').lower()
            if code == 'PARSE':
                hint = (
                    f'BillAvenue returned a malformed/partial MDM payload (missing responseCode). '
                    f'Existing {live.upper()} synced catalog remains usable; retry with a smaller ID list '
                    f'(e.g. 25 at a time) or verify upstream gateway response format.'
                )
            elif code == '202':
                hint = (
                    f'BillAvenue rejected the MDM request size/format (code {code}). '
                    f'Try syncing fewer biller IDs per call (25–40). Existing {live.upper()} catalog remains usable.'
                )
            elif code == '205' and ('de001' in msg_l or 'invalid enc' in msg_l):
                hint = (
                    f'BillAvenue rejected the encrypted UAT/PROD MDM request (DE001 — Invalid ENC). '
                    f'Open BBPS Console → BillAvenue Settings for {live.upper()}, re-paste the full Working Key '
                    f'(and Access Code / IV) from the BillAvenue portal for this institute, save, then retry Sync. '
                    f'Existing {live.upper()} synced catalog remains usable.'
                )
            else:
                hint = (
                    f'BillAvenue blocked live MDM call for this {live.upper()} config/agent at this moment. '
                    f'Existing {live.upper()} synced catalog remains usable; complete prerequisites and retry sync later.'
                )
            data['hint'] = hint
            return Response(
                {'success': False, 'data': data, 'message': str(e), 'errors': []},
                status=200,
            )
        return Response({'success': False, 'data': data or None, 'message': str(e), 'errors': []}, status=400)
    except BillAvenueEntitlementError as e:
        logger.warning('sync-billers BillAvenue entitlement (205): %s', e)
        msg_l = str(e or '').lower()
        if 'de001' in msg_l or 'invalid enc' in msg_l:
            hint = (
                'BillAvenue rejected the encrypted MDM request (DE001 — Invalid ENC). '
                'Open BBPS Console → BillAvenue Settings for this environment, re-paste the full Working Key '
                '(and Access Code / IV) from the BillAvenue portal for this institute, save, then retry Sync.'
            )
        else:
            hint = (
                'BillAvenue MDM entitlement/profile mismatch for this institute or agent. '
                'Ask BillAvenue to confirm MDM access for your accessCode/instituteId/agentId and server egress IP.'
            )
        return Response(
            {
                'success': False,
                'data': {
                    'billavenue_code': '205',
                    'hint': hint,
                },
                'message': str(e),
                'errors': ['205'],
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except BillAvenueClientError as e:
        return Response({'success': False, 'data': None, 'message': str(e), 'errors': []}, status=400)


def _serialize_import_job(job: BbpsMdmImportJob) -> dict:
    data = BbpsMdmImportJobSerializer(job).data
    data['quota'] = sync_quota_snapshot(job.environment)
    return data


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def mdm_import_upload_view(request):
    """Upload BillAvenue MDM Excel and queue/sync biller IDs for one catalog env."""
    upload = request.FILES.get('file') or request.FILES.get('excel')
    if not upload:
        return Response(
            {'success': False, 'data': None, 'message': 'Excel file is required (field: file)', 'errors': ['file']},
            status=400,
        )
    env_param = str(request.data.get('environment') or request.data.get('mode') or '').strip().lower()
    if env_param not in ('uat', 'prod'):
        return Response(
            {'success': False, 'data': None, 'message': 'environment must be uat or prod', 'errors': ['environment']},
            status=400,
        )
    auto_drain = str(request.data.get('auto_drain', 'true')).strip().lower() not in ('0', 'false', 'no')
    try:
        from apps.bbps.catalog.mdm_import.processor import create_job_from_upload

        result = create_job_from_upload(
            file_obj=upload,
            filename=getattr(upload, 'name', '') or 'upload.xlsx',
            environment=env_param,
            user=request.user,
            auto_drain=auto_drain,
            invalidate_cache=_invalidate_bbps_user_catalog_cache,
        )
    except ValueError as exc:
        return Response({'success': False, 'data': None, 'message': str(exc), 'errors': []}, status=400)
    except Exception as exc:
        logger.exception('mdm-import upload failed')
        return Response({'success': False, 'data': None, 'message': f'Import failed: {exc}', 'errors': []}, status=400)

    job = result['job']
    return Response(
        {
            'success': True,
            'data': {
                'job': _serialize_import_job(job),
                'seed': result.get('seed') or {},
                'drain': result.get('drain') or {},
                'quota': result.get('quota') or sync_quota_snapshot(env_param),
            },
            'message': (
                f'Imported {job.total_ids} biller ID(s) into {env_param.upper()} queue'
                + (f'; {job.synced_ids} synced today, {job.pending_ids} pending' if job.pending_ids else '')
            ),
            'errors': [],
        },
        status=201,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def mdm_import_jobs_list_view(request):
    env_param = str(request.query_params.get('environment') or request.query_params.get('mode') or '').strip().lower()
    qs = BbpsMdmImportJob.objects.filter(is_deleted=False).order_by('-created_at')
    if env_param in ('uat', 'prod'):
        qs = qs.filter(environment=env_param)
    rows = list(qs[:30])
    return Response(
        {
            'success': True,
            'data': {
                'jobs': [_serialize_import_job(j) for j in rows],
                'quota': sync_quota_snapshot(env_param if env_param in ('uat', 'prod') else None),
            },
            'message': 'MDM import jobs retrieved',
            'errors': [],
        },
        status=200,
    )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def mdm_import_job_detail_view(request, pk: int):
    job = BbpsMdmImportJob.objects.filter(pk=pk, is_deleted=False).first()
    if not job:
        return Response({'success': False, 'data': None, 'message': 'Import job not found', 'errors': []}, status=404)

    if request.method == 'DELETE':
        from apps.bbps.catalog.mdm_import.processor import destroy_job

        reason = str((request.data or {}).get('reason') or request.query_params.get('reason') or '').strip()
        try:
            out = destroy_job(job.pk, reason=reason or 'Destroyed by admin from Provider Governance')
        except ValueError as exc:
            return Response({'success': False, 'data': None, 'message': str(exc), 'errors': []}, status=400)
        return Response(
            {
                'success': True,
                'data': out,
                'message': f'Import job #{pk} destroyed. Pending IDs will not be processed.',
                'errors': [],
            },
            status=200,
        )

    items = BbpsMdmImportItem.objects.filter(job=job, is_deleted=False).order_by('id')[:200]
    failed = BbpsMdmImportItem.objects.filter(job=job, is_deleted=False, status='failed').order_by('-updated_at')[:50]
    return Response(
        {
            'success': True,
            'data': {
                'job': _serialize_import_job(job),
                'sample_items': BbpsMdmImportItemSerializer(items, many=True).data,
                'failed_items': BbpsMdmImportItemSerializer(failed, many=True).data,
            },
            'message': 'MDM import job retrieved',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def mdm_import_job_destroy_view(request, pk: int):
    """POST alias for destroy (same as DELETE) for simpler frontend clients."""
    from apps.bbps.catalog.mdm_import.processor import destroy_job

    job = BbpsMdmImportJob.objects.filter(pk=pk, is_deleted=False).first()
    if not job:
        return Response({'success': False, 'data': None, 'message': 'Import job not found', 'errors': []}, status=404)
    reason = str((request.data or {}).get('reason') or '').strip()
    try:
        out = destroy_job(job.pk, reason=reason or 'Destroyed by admin from Provider Governance')
    except ValueError as exc:
        return Response({'success': False, 'data': None, 'message': str(exc), 'errors': []}, status=400)
    return Response(
        {
            'success': True,
            'data': out,
            'message': f'Import job #{pk} destroyed. Pending IDs will not be processed.',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def mdm_import_job_process_view(request, pk: int):
    from apps.bbps.catalog.mdm_import.processor import drain_job

    job = BbpsMdmImportJob.objects.filter(pk=pk, is_deleted=False).first()
    if not job:
        return Response({'success': False, 'data': None, 'message': 'Import job not found', 'errors': []}, status=404)
    try:
        drain = drain_job(job.pk, user=request.user, invalidate_cache=_invalidate_bbps_user_catalog_cache)
    except ValueError as exc:
        return Response({'success': False, 'data': None, 'message': str(exc), 'errors': []}, status=400)
    job.refresh_from_db()
    return Response(
        {
            'success': True,
            'data': {'job': _serialize_import_job(job), 'drain': drain},
            'message': f'Processed job #{job.pk}',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def mdm_import_process_pending_view(request):
    from apps.bbps.catalog.mdm_import.processor import process_pending_jobs

    env_param = str((request.data or {}).get('environment') or request.query_params.get('environment') or '').strip().lower()
    env = env_param if env_param in ('uat', 'prod') else None
    out = process_pending_jobs(
        environment=env,
        max_jobs=int((request.data or {}).get('max_jobs') or 5),
        user=request.user,
        invalidate_cache=_invalidate_bbps_user_catalog_cache,
    )
    return Response(
        {
            'success': True,
            'data': {**out, 'quota': sync_quota_snapshot(env)},
            'message': f'Processed {out.get("processed", 0)} pending import job(s)',
            'errors': [],
        },
        status=200,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def sync_usage_today_view(request):
    env_param = str(request.query_params.get('environment') or request.query_params.get('mode') or '').strip().lower()
    env = env_param if env_param in ('uat', 'prod') else None
    return Response(
        {'success': True, 'data': _sync_quota_snapshot(env), 'message': 'Sync usage retrieved', 'errors': []},
        status=200,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def sync_usage_history_view(request):
    rows = BbpsSyncUsageLog.objects.filter(is_deleted=False).order_by('-usage_date', '-environment')[:60]
    return Response(
        {
            'success': True,
            'data': {'history': BbpsSyncUsageLogSerializer(rows, many=True).data},
            'message': 'Sync usage history retrieved',
            'errors': [],
        },
        status=200,
    )


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
    # End users often paste internal service ids (PMBBPS...) from My Bills. Map to real CC... txn_ref_id for provider.
    if str(payload.get('trackingType') or '') == 'TRANS_REF_ID':
        tv = str(payload.get('trackingValue') or '').strip()
        if tv.upper().startswith('PMBBPS'):
            attempt = (
                BbpsPaymentAttempt.objects.filter(service_id=tv, is_deleted=False)
                .order_by('-created_at')
                .first()
            )
            if attempt and str(getattr(attempt, 'txn_ref_id', '') or '').strip():
                payload['trackingValue'] = str(attempt.txn_ref_id).strip()
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
    except BillAvenueTransportError as exc:
        return Response({'success': False, 'data': None, 'message': str(exc), 'errors': []}, status=503)
    txns = data.get('txnList') or data.get('transactionStatusResp', {}).get('txnList') or []
    from apps.bbps.transaction_query_enrich import enrich_transactions_for_query

    txns = enrich_transactions_for_query(request.user, txns)
    return Response(
        {
            'success': True,
            'data': {'transactions': txns, 'raw': data},
            'message': 'Transaction query completed',
            'errors': [],
        },
        status=200,
    )


def _complaint_register_post_body(request) -> dict:
    """Normalize DRF request.data (dict or QueryDict) for logging."""
    raw = getattr(request, 'data', None)
    if raw is None:
        return {}
    if hasattr(raw, 'dict'):
        try:
            return dict(raw.dict())
        except Exception:
            pass
    if isinstance(raw, dict):
        return raw
    try:
        return dict(raw)
    except Exception:
        return {}


def _complaint_register_request_summary(data) -> dict:
    """Safe fields for ops logs (avoid logging full free-text complaint body)."""
    if not isinstance(data, dict):
        return {}
    out: dict = {}
    tid = str(data.get('txn_ref_id') or '').strip()
    if tid:
        out['txn_ref_id_prefix'] = tid[:8] + ('…' if len(tid) > 8 else '')
        out['txn_ref_id_len'] = len(tid)
    disp = str(data.get('complaint_disposition') or '').strip()
    if disp:
        out['complaint_disposition_prefix'] = disp[:60] + ('…' if len(disp) > 60 else '')
    desc = str(data.get('complaint_desc') or data.get('complain_desc') or '').strip()
    if desc:
        out['complaint_desc_len'] = len(desc)
    return out


def _log_complaint_register_failure(*, request, http_status: int, message: str, **extra):
    payload = {
        'event': 'bbps_complaint_register_failed',
        'user_id': getattr(request.user, 'pk', None),
        'http_status': http_status,
        'message': str(message or '')[:2000],
        **_complaint_register_request_summary(_complaint_register_post_body(request)),
    }
    payload.update({k: v for k, v in extra.items() if v is not None})
    try:
        line = json.dumps(payload, default=str, ensure_ascii=False)
    except Exception:
        line = str(payload)
    logger.warning('%s', line)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complaint_register_view(request):
    ser = ComplaintRegisterSerializer(data=request.data)
    if not ser.is_valid():
        _log_complaint_register_failure(
            request=request,
            http_status=400,
            message='Invalid complaint request',
            validation_errors=json.loads(json.dumps(ser.errors, default=str)),
        )
        return Response({'success': False, 'data': None, 'message': 'Invalid complaint request', 'errors': ser.errors}, status=400)
    try:
        row = register_complaint(user=request.user, **ser.validated_data)
    except TransactionFailed as exc:
        msg = str(exc)
        status_code = (
            409
            if (
                'duplicate complaint' in msg.lower()
                or 'already has an open complaint' in msg.lower()
                or 'this transaction already has an open complaint' in msg.lower()
                or 'billavenue usually rejects' in msg.lower()
                or 'billavenue reports this transaction already has' in msg.lower()
            )
            else 400
        )
        _log_complaint_register_failure(request=request, http_status=status_code, message=msg)
        return Response({'success': False, 'data': None, 'message': msg, 'errors': []}, status=status_code)
    except BillAvenueClientError as exc:
        raw = str(exc)
        friendly = _friendly_complaint_error_message(raw)
        ba_rid = str(getattr(exc, 'billavenue_request_id', '') or '').strip()
        _log_complaint_register_failure(
            request=request,
            http_status=400,
            message=friendly,
            billavenue_error_detail=raw[:2000],
            billavenue_request_id=ba_rid or None,
        )
        err_body = {
            'success': False,
            'message': friendly,
            'errors': [],
            'data': {'billavenue_request_id': ba_rid} if ba_rid else {},
        }
        return Response(err_body, status=400)
    except BillAvenueTransportError as exc:
        _log_complaint_register_failure(request=request, http_status=503, message=str(exc))
        return Response({'success': False, 'data': None, 'message': str(exc), 'errors': []}, status=503)
    msg = 'Complaint registered with BBPS (BillAvenue). Use the complaint ID to track status.'
    code = 201
    manual = str(row.complaint_status or '') == 'MANUAL_ESCALATION_REQUIRED'
    if manual:
        msg = (
            'BillAvenue did not accept automated complaint registration for this transaction (manual escalation path). '
            'Your details were saved in mPayHub for your records. '
            'To proceed, email cms@billavenue.com with your B-Connect transaction ID (CC…), disposition, and description.'
        )
        code = 202
        logger.info(
            '%s',
            json.dumps(
                {
                    'event': 'bbps_complaint_register_manual_escalation',
                    'user_id': getattr(request.user, 'pk', None),
                    'complaint_id': str(row.complaint_id or ''),
                    'http_status': 202,
                },
                default=str,
                ensure_ascii=False,
            ),
        )
    return Response(
        {
            'success': True,
            'data': {
                'complaint_id': row.complaint_id,
                'status': row.complaint_status,
                # Explicit flags so clients do not treat 202 the same as a live BBPS complaint id.
                'manual_escalation_required': manual,
                'provider_complaint_registered': not manual,
            },
            'message': msg,
            'errors': [],
        },
        status=code,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complaint_track_view(request):
    ser = ComplaintTrackSerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid complaint track request', 'errors': ser.errors}, status=400)
    complaint = BbpsComplaint.objects.filter(complaint_id=ser.validated_data['complaint_id'], user=request.user, is_deleted=False).first()
    if not complaint:
        return Response(
            {
                'success': False,
                'data': {
                    'hint': 'Use the Complaint ID from your registration confirmation or open Complaint Management → '
                    'Complaint History. Tracking only works for complaints saved on this account.'
                },
                'message': 'Complaint not found for this account.',
                'errors': [],
            },
            status=404,
        )
    resp = track_complaint(complaint=complaint)
    manual = str(complaint.complaint_status or '') == 'MANUAL_ESCALATION_REQUIRED' or str(
        complaint.complaint_id or ''
    ).upper().startswith('MANUAL-')
    track_msg = 'Complaint status fetched from BBPS.'
    if manual:
        track_msg = (
            'This is a local reference only (BillAvenue manual escalation). '
            'It was not submitted as a standard BBPS complaint id—use email to cms@billavenue.com as instructed.'
        )
    return Response(
        {
            'success': True,
            'data': {
                'response': resp,
                'manual_escalation_required': manual,
                'provider_track_eligible': not manual,
            },
            'message': track_msg,
            'errors': [],
        },
        status=200,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def complaint_history_view(request):
    ser = ComplaintHistoryQuerySerializer(data=request.query_params or {})
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid complaint history request', 'errors': ser.errors}, status=400)

    status_filter = str(ser.validated_data.get('status') or '').strip()
    q = str(ser.validated_data.get('q') or '').strip()
    page = int(ser.validated_data.get('page') or 1)
    page_size = int(ser.validated_data.get('page_size') or 20)
    include_events = bool(ser.validated_data.get('include_events'))

    rows = (
        BbpsComplaint.objects.filter(user=request.user, is_deleted=False)
        .select_related('attempt__bill_payment')
        .prefetch_related('events')
        .order_by('-created_at')
    )
    if status_filter:
        rows = rows.filter(complaint_status__iexact=status_filter)
    if q:
        rows = rows.filter(
            Q(complaint_id__icontains=q)
            | Q(txn_ref_id__icontains=q)
            | Q(complaint_desc__icontains=q)
            | Q(complaint_disposition__icontains=q)
            | Q(attempt__service_id__icontains=q)
            | Q(billavenue_request_id__icontains=q)
            | Q(attempt__request_id__icontains=q)
        )

    total = rows.count()
    start = (page - 1) * page_size
    end = start + page_size
    paginated = rows[start:end]
    payload = ComplaintHistoryItemSerializer(
        paginated,
        many=True,
        context={'include_events': include_events},
    ).data

    status_counts = {}
    for item in (
        BbpsComplaint.objects.filter(user=request.user, is_deleted=False)
        .values('complaint_status')
        .annotate(total=Count('id'))
    ):
        key = str(item.get('complaint_status') or '').strip() or 'UNKNOWN'
        status_counts[key] = int(item.get('total') or 0)

    return Response(
        {
            'success': True,
            'data': {
                'complaints': payload,
                'total': total,
                'page': page,
                'page_size': page_size,
                'has_next': end < total,
                'status_counts': status_counts,
            },
            'message': 'Complaint history fetched',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complaint_refresh_status_view(request):
    ser = ComplaintTrackSerializer(data=request.data or {})
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid complaint refresh request', 'errors': ser.errors}, status=400)
    complaint = BbpsComplaint.objects.filter(
        complaint_id=ser.validated_data['complaint_id'],
        user=request.user,
        is_deleted=False,
    ).first()
    if not complaint:
        return Response({'success': False, 'data': None, 'message': 'Complaint not found', 'errors': []}, status=404)

    resp = track_complaint(complaint=complaint)
    manual = str(complaint.complaint_status or '').upper() == 'MANUAL_ESCALATION_REQUIRED' or str(
        complaint.complaint_id or ''
    ).upper().startswith('MANUAL-')
    track_msg = 'Complaint status refreshed from BBPS.'
    if manual:
        track_msg = (
            'This complaint is in manual escalation mode. '
            'BillAvenue will not return hub-side status updates for MANUAL references.'
        )

    return Response(
        {
            'success': True,
            'data': {
                'complaint_id': complaint.complaint_id,
                'status': complaint.complaint_status,
                'response': resp,
                'manual_escalation_required': manual,
                'provider_track_eligible': not manual,
            },
            'message': track_msg,
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def plan_pull_view(request):
    ser = PlanPullSerializer(data=request.data or {})
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid plan pull request', 'errors': ser.errors}, status=400)
    requested_ids = [str(x or '').strip() for x in (ser.validated_data.get('biller_ids') or []) if str(x or '').strip()]
    masters = {
        m.biller_id: m
        for m in biller_master_qs_for_env().filter(biller_id__in=requested_ids)
    } if requested_ids else {}
    eligible_ids = []
    skipped_ids = []
    for bid in requested_ids:
        m = masters.get(bid)
        req = str(getattr(m, 'plan_mdm_requirement', '') or '').strip().upper()
        if req in ('OPTIONAL', 'MANDATORY', 'SUPPORTED', 'Y', 'YES', 'TRUE', '1'):
            eligible_ids.append(bid)
        else:
            skipped_ids.append(bid)
    if requested_ids and not eligible_ids:
        return Response(
            {
                'success': True,
                'data': {
                    'run_id': None,
                    'plan_count': 0,
                    'response': {},
                    'requested_biller_ids': requested_ids,
                    'processed_biller_ids': [],
                    'skipped_biller_ids': skipped_ids,
                    'warning': 'Selected billers are not plan-enabled by MDM requirement.',
                },
                'message': 'Plan pull skipped',
                'errors': [],
            },
            status=200,
        )
    try:
        out = pull_biller_plans(biller_ids=eligible_ids if requested_ids else (ser.validated_data.get('biller_ids') or []))
        if skipped_ids:
            out['skipped_biller_ids'] = skipped_ids
        return Response({'success': True, 'data': out, 'message': 'Plan pull completed', 'errors': []}, status=200)
    except BillAvenueClientError as e:
        msg = str(e or '')
        low = msg.lower()
        # Optional-plan billers may legitimately return no-plan payloads (e.g., PP002/205 variants).
        if ('pp002' in low or 'no plan' in low) and requested_ids and all(
            str(getattr(masters.get(bid), 'plan_mdm_requirement', '') or '').strip().upper() == 'OPTIONAL'
            for bid in requested_ids
        ):
            return Response(
                {
                    'success': True,
                    'data': {
                        'run_id': None,
                        'plan_count': 0,
                        'response': {},
                        'requested_biller_ids': requested_ids,
                        'processed_biller_ids': eligible_ids,
                        'skipped_biller_ids': skipped_ids,
                        'warning': 'No plan data returned for optional-plan biller(s).',
                    },
                    'message': 'Plan pull completed (no plans available)',
                    'errors': [],
                },
                status=200,
            )
        return Response({'success': False, 'data': None, 'message': _friendly_plan_pull_error_message(msg), 'errors': []}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def provider_float_view(request):
    """GET /api/bbps/admin/provider-float/ — status + paginated ledger."""
    from datetime import datetime

    from apps.bbps.service_flow.provider_float import get_float_status, list_ledger

    env_param = str(request.query_params.get('environment') or request.query_params.get('mode') or '').strip().lower()
    env = normalize_billavenue_mode(env_param) if env_param in ('uat', 'prod') else active_bbps_environment()

    def _parse_date(raw):
        if not raw:
            return None
        raw = str(raw).strip()
        for fmt in ('%Y-%m-%d', '%d-%m-%Y'):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        return None

    try:
        page = int(request.query_params.get('page') or 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.query_params.get('page_size') or 50)
    except (TypeError, ValueError):
        page_size = 50

    status_data = get_float_status(env)
    ledger = list_ledger(
        environment=env,
        entry_type=str(request.query_params.get('entry_type') or ''),
        date_from=_parse_date(request.query_params.get('date_from')),
        date_to=_parse_date(request.query_params.get('date_to')),
        page=page,
        page_size=page_size,
    )
    return Response(
        {
            'success': True,
            'data': {'float': status_data, 'ledger': ledger},
            'message': 'Provider float retrieved',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def provider_float_set_view(request):
    """POST /api/bbps/admin/provider-float/set/ — override tracked balance."""
    from apps.bbps.service_flow.provider_float import set_float_balance

    data = request.data or {}
    env_param = str(data.get('environment') or data.get('mode') or '').strip().lower()
    env = normalize_billavenue_mode(env_param) if env_param in ('uat', 'prod') else active_bbps_environment()
    try:
        out = set_float_balance(
            admin_user=request.user,
            new_balance=data.get('new_balance'),
            remarks=str(data.get('remarks') or ''),
            environment=env,
        )
    except ValueError as exc:
        return Response(
            {'success': False, 'data': None, 'message': str(exc), 'errors': [str(exc)]},
            status=400,
        )
    return Response(
        {
            'success': True,
            'data': {'float': out},
            'message': f"Provider float updated to ₹{out.get('balance')}",
            'errors': [],
        },
        status=200,
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])
def provider_float_settings_view(request):
    """PATCH /api/bbps/admin/provider-float/settings/ — threshold + enforcement."""
    from apps.bbps.service_flow.provider_float import update_float_settings

    data = request.data or {}
    env_param = str(data.get('environment') or data.get('mode') or '').strip().lower()
    env = normalize_billavenue_mode(env_param) if env_param in ('uat', 'prod') else active_bbps_environment()
    kwargs = {'admin_user': request.user, 'environment': env}
    if 'low_balance_threshold' in data:
        kwargs['low_balance_threshold'] = data.get('low_balance_threshold')
    if 'enforcement_enabled' in data:
        kwargs['enforcement_enabled'] = data.get('enforcement_enabled')
    try:
        out = update_float_settings(**kwargs)
    except ValueError as exc:
        return Response(
            {'success': False, 'data': None, 'message': str(exc), 'errors': [str(exc)]},
            status=400,
        )
    return Response(
        {
            'success': True,
            'data': {'float': out},
            'message': 'Provider float settings updated',
            'errors': [],
        },
        status=200,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def deposit_enquiry_view(request):
    """Run BillAvenue deposit enquiry and persist a snapshot for reporting."""
    from apps.bbps.service_flow.deposit_service import enquire_deposits as run_deposit_enquiry

    ser = DepositEnquirySerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid deposit enquiry request', 'errors': ser.errors},
            status=400,
        )
    try:
        out = run_deposit_enquiry(**ser.validated_data, admin_user=request.user)
        return Response(
            {
                'success': True,
                'data': out,
                'message': (
                    f"Deposit enquiry completed — balance {out.get('currency', 'INR')} "
                    f"{out.get('current_balance')} · {len(out.get('transactions') or [])} txn(s)"
                ),
                'errors': [],
            },
            status=200,
        )
    except ValueError as e:
        return Response({'success': False, 'data': None, 'message': str(e), 'errors': [str(e)]}, status=400)
    except BillAvenueClientError as e:
        # Failed runs are still stored; surface latest matching snapshot if present.
        from apps.bbps.models import BbpsDepositEnquirySnapshot
        from apps.bbps.service_flow.deposit_service import serialize_snapshot

        shot = (
            BbpsDepositEnquirySnapshot.objects.filter(
                is_deleted=False, status='FAILED', performed_by=request.user
            )
            .order_by('-created_at')
            .first()
        )
        data = {'snapshot': serialize_snapshot(shot, include_payload=True)} if shot else None
        return Response(
            {'success': False, 'data': data, 'message': str(e), 'errors': [str(e)]},
            status=400,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def deposit_enquiry_history_view(request):
    """Paginated deposit enquiry history + agent options for the ops form."""
    from datetime import datetime

    from apps.bbps.service_flow.deposit_service import list_deposit_enquiries

    def _parse_date(raw):
        if not raw:
            return ''
        raw = str(raw).strip()
        for fmt in ('%Y-%m-%d', '%d-%m-%Y'):
            try:
                return datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                continue
        return ''

    try:
        page = int(request.query_params.get('page') or 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.query_params.get('page_size') or 25)
    except (TypeError, ValueError):
        page_size = 25

    env_param = str(request.query_params.get('environment') or '').strip().lower()
    data = list_deposit_enquiries(
        environment=env_param if env_param in ('uat', 'prod') else None,
        page=page,
        page_size=page_size,
        date_from=_parse_date(request.query_params.get('date_from')),
        date_to=_parse_date(request.query_params.get('date_to')),
        status=str(request.query_params.get('status') or ''),
    )
    return Response(
        {'success': True, 'data': data, 'message': 'Deposit enquiry history retrieved', 'errors': []},
        status=200,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def deposit_enquiry_detail_view(request, snapshot_id: int):
    from apps.bbps.service_flow.deposit_service import get_deposit_enquiry

    try:
        data = get_deposit_enquiry(snapshot_id)
    except LookupError as e:
        return Response({'success': False, 'data': None, 'message': str(e), 'errors': []}, status=404)
    return Response(
        {'success': True, 'data': {'snapshot': data}, 'message': 'Deposit enquiry detail retrieved', 'errors': []},
        status=200,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def uat_readiness_checklist_view(request):
    try:
        # integration_health_view is also DRF-decorated; pass raw Django HttpRequest to avoid
        # nested DRF Request wrapping assertion errors.
        base_request = request._request if hasattr(request, '_request') else request
        health_resp = integration_health_view(base_request)
        health_payload = getattr(health_resp, 'data', {}) or {}
        health = health_payload.get('data', {}) if isinstance(health_payload, dict) else {}
        if not isinstance(health, dict):
            health = {}

        readiness = get_setup_readiness()
        if not isinstance(readiness, dict):
            readiness = {}

        stats = readiness.get('stats', {}) if isinstance(readiness.get('stats', {}), dict) else {}
        blockers_from_health = health.get('blockers', []) if isinstance(health.get('blockers', []), list) else []

        checklist = [
            {'key': 'active_config', 'ok': 'active_config' not in blockers_from_health},
            {'key': 'agent_profile', 'ok': 'agent_profile' not in blockers_from_health},
            {'key': 'entitlement_probe', 'ok': health.get('entitlement_probe_ok') is not False},
            {'key': 'mdm_synced', 'ok': stats.get('mdm_biller_count', 0) > 0},
            {'key': 'provider_mapping', 'ok': stats.get('mapping_count', 0) > 0},
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
    except Exception as exc:
        logger.exception('uat-readiness failed: %s', exc)
        return Response(
            {
                'success': False,
                'data': {
                    'checklist': [
                        {'key': 'active_config', 'ok': False},
                        {'key': 'agent_profile', 'ok': False},
                        {'key': 'entitlement_probe', 'ok': False},
                        {'key': 'mdm_synced', 'ok': False},
                        {'key': 'provider_mapping', 'ok': False},
                    ],
                    'blockers': ['active_config', 'agent_profile', 'entitlement_probe', 'mdm_synced', 'provider_mapping'],
                    'go_live_blocked': True,
                    'latest_probe_message': '',
                    'latest_mdm_error': '',
                },
                'message': 'UAT readiness temporarily unavailable. Please retry.',
                'errors': [str(exc)],
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
        prior_status = str(attempt.status or '').upper()
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

        try:
            from apps.bbps.service_flow.provider_float import credit_float_for_refund, debit_float_for_payment
            from apps.bbps.service_flow.status_service import _float_amount_for_attempt

            sid = attempt.service_id or (attempt.bill_payment.service_id if attempt.bill_payment_id else '')
            amt = _float_amount_for_attempt(attempt)
            if code == '000' and prior_status != 'SUCCESS':
                debit_float_for_payment(sid, amt, payment_attempt=attempt, remarks=f'Webhook SUCCESS {sid}')
            elif code == '300' and prior_status not in ('REFUNDED', 'REVERSED'):
                credit_float_for_refund(sid, amt, payment_attempt=attempt, remarks=f'Webhook REFUNDED {sid}')
        except Exception:
            logger.exception('provider float webhook hook failed attempt=%s', attempt.pk)

        from apps.bbps.notifications import notify_payment_attempt_status

        notify_payment_attempt_status(attempt, source='webhook_callback')
    evt.processed = True
    evt.processed_at = timezone.now()
    evt.save(update_fields=['processed', 'processed_at', 'updated_at'])
    return Response({'success': True, 'data': None, 'message': 'callback accepted', 'errors': []}, status=200)
