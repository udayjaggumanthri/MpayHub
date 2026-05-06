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
from apps.bbps.service_flow.bbps_wallet_charge import resolve_bbps_wallet_service_charge
from apps.bbps.service_flow.commission_service import resolve_commission_for_payment
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
from apps.bbps.service_flow.provider_policy import bootstrap_default_biller_policy_if_missing
from apps.bbps.service_flow.compliance import (
    bbps_channel_accepts_payment_mode,
    display_payment_modes_for_channel,
)
from apps.core.exceptions import InsufficientBalance, TransactionFailed
from apps.core.financial_access import assert_can_perform_financial_txn
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
    cfg = BillAvenueConfig.objects.filter(is_deleted=False, enabled=True, is_active=True).first()
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
            'Fetch the bill again and pay immediately without changing tags, amount, or plan selection.'
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
        return 'Plan pull is not enabled for this BillAvenue profile. Check agent/profile entitlement in admin.'
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
    master = BbpsBillerMaster.objects.filter(biller_id=biller_id, is_deleted=False).first()
    plan_req = str(getattr(master, 'plan_mdm_requirement', '') or '').strip() if master else ''
    fetch_req = str(getattr(master, 'biller_fetch_requirement', '') or '').strip() if master else ''
    fetch_req_upper = fetch_req.upper()
    quickpay_only = 'QUICKPAY' in fetch_req_upper and (
        'ONLY' in fetch_req_upper or 'NOT SUPPORTED' in fetch_req_upper or 'UNSUPPORTED' in fetch_req_upper
    )
    additional_info_schema = get_biller_additional_info_schema(biller_id)
    plans_lite, plans_truncated = get_biller_plans_lite(biller_id, limit=100)
    return Response(
        {
            'success': True,
            'data': {
                'biller_id': biller_id,
                'input_schema': schema,
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
            validate_biller_inputs(biller_id=biller_id, input_map=input_map)
            flow = fetch_bill_with_cache(
                user=request.user,
                biller_id=biller_id,
                customer_info={'customerMobile': derived_mobile},
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
            msg = _friendly_fetch_error_message(str(e))
            is_timeout = 'TIMEOUT' in str(e).upper() or 'TIMED OUT' in str(e).upper()
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE if is_timeout else status.HTTP_400_BAD_REQUEST
            return bbps_error_response(
                msg,
                code='BBPS_FETCH_TIMEOUT' if is_timeout else 'BBPS_FETCH_TRANSPORT',
                retryable=bool(is_timeout),
                http_status=http_status,
            )
        except BillAvenueClientError as e:
            raw = str(e)
            low = raw.lower()
            if 'timeout' in low or 'timed out' in low:
                return bbps_error_response(
                    _friendly_fetch_error_message(raw),
                    code='BBPS_FETCH_TIMEOUT',
                    retryable=True,
                    http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            if 'errorcode": "brp046' in low or 'only quickpay permitted' in low or 'quickpay permitted' in low:
                return bbps_error_response(
                    _friendly_fetch_error_message(raw),
                    code='BBPS_FETCH_QUICKPAY_ONLY',
                    retryable=False,
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            return bbps_error_response(
                _friendly_fetch_error_message(raw),
                code='BBPS_FETCH_PROVIDER',
                retryable=False,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        except TransactionFailed as e:
            return bbps_error_response(
                _friendly_fetch_error_message(str(e)),
                code='BBPS_FETCH_VALIDATION',
                retryable=False,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return bbps_error_response(
                _friendly_fetch_error_message(str(e)),
                code='BBPS_FETCH_FAILED',
                retryable=False,
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
    assert_can_perform_financial_txn(request.user)
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
        except TransactionFailed as e:
            raw = str(e)
            low = raw.lower()
            if ('e204' in low and 'already been used' in low) or 'request id is already been used' in low:
                return bbps_error_response(
                    _friendly_pay_error_message(raw),
                    code='BBPS_PAY_REQUEST_ID_REUSED',
                    retryable=True,
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            if 'e212' in low or 'additionalinfo value mismatch' in low:
                return bbps_error_response(
                    _friendly_pay_error_message(raw),
                    code='BBPS_PAY_ADDITIONAL_INFO_MISMATCH',
                    retryable=True,
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            return bbps_error_response(
                _friendly_pay_error_message(raw),
                code='BBPS_PAY_DECLINED',
                retryable=False,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception('pay-bill unexpected failure: %s', e)
            return bbps_error_response(
                _friendly_pay_error_message(str(e)),
                code='BBPS_PAY_FAILED',
                retryable=False,
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
    try:
        page = int(request.query_params.get('page', 1))
    except Exception:
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid page parameter', 'errors': {'page': ['Must be an integer >= 1.']}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if page < 1:
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid page parameter', 'errors': {'page': ['Must be an integer >= 1.']}},
            status=status.HTTP_400_BAD_REQUEST,
        )
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


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_payment_mapping_view(request, biller_id: str):
    from apps.bbps.service_flow.compliance import bbps_channel_accepts_payment_mode
    from apps.bbps.service_flow.provider_policy import provider_policy_decision_for_combo

    bid = str(biller_id or '').strip()
    master = BbpsBillerMaster.objects.filter(is_deleted=False, biller_id=bid).first()
    if not master:
        return Response({'success': False, 'data': None, 'message': 'Biller not found', 'errors': []}, status=404)
    cfg = BillAvenueConfig.objects.filter(is_deleted=False, enabled=True, is_active=True).first()
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


def _invalidate_provider_cache(*category_codes: str):
    for code in category_codes:
        if code:
            cache.delete(f"bbps:providers:{normalize_category_code(code)}")


def _invalidate_bbps_user_catalog_cache():
    category_codes = set()
    category_codes.update(
        str(code or '').strip()
        for code in BbpsServiceCategory.objects.filter(is_deleted=False).values_list('code', flat=True)
    )
    category_codes.update(
        str(code or '').strip()
        for code in BbpsBillerMaster.objects.filter(is_deleted=False).values_list('biller_category', flat=True)
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
            payload: dict = {}
            if probe_agent:
                payload['agentId'] = str(probe_agent.agent_id or '').strip()
            # Agent-only biller_info often returns code=001; reuse latest cached biller so the probe matches sync MDM.
            cached_biller = (
                BbpsBillerMaster.objects.filter(is_deleted=False)
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
    if request.method == 'GET':
        category = request.query_params.get('category')
        q = str(request.query_params.get('q') or '').strip()
        active = str(request.query_params.get('active') or '').strip().lower()
        try:
            page = max(1, int(request.query_params.get('page') or 1))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = max(1, min(100, int(request.query_params.get('page_size') or 25)))
        except (TypeError, ValueError):
            page_size = 25
        qs = BbpsBillerMaster.objects.filter(is_deleted=False).order_by('biller_name')
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
        return Response(
            {
                'success': True,
                'data': {
                    'billers': BbpsBillerMasterLiteSerializer(rows, many=True).data,
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
    ser = BbpsBillerMasterAdminSerializer(data=request.data)
    if not ser.is_valid():
        return Response({'success': False, 'data': None, 'message': 'Invalid biller payload', 'errors': ser.errors}, status=400)
    row = ser.save(source_type='manual', is_active_local=True, updated_by_admin_at=timezone.now(), version=1)
    bootstrap_default_biller_policy_if_missing(biller=row)
    auto_plan_pull = _maybe_auto_pull_plans_for_billers([row.biller_id])
    _invalidate_bbps_user_catalog_cache()
    return Response({'success': True, 'data': {'biller': BbpsBillerMasterAdminSerializer(row).data, 'auto_plan_pull': auto_plan_pull}, 'message': 'Biller created', 'errors': []}, status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def biller_master_admin_detail_view(request, pk: int):
    row = BbpsBillerMaster.objects.filter(pk=pk, is_deleted=False).first()
    if not row:
        return Response({'success': False, 'data': None, 'message': 'Biller not found', 'errors': []}, status=404)
    if request.method == 'DELETE':
        row.soft_deleted_at = timezone.now()
        row.is_active_local = False
        row.updated_by_admin_at = timezone.now()
        row.save(update_fields=['soft_deleted_at', 'is_active_local', 'updated_by_admin_at', 'updated_at'])
        _invalidate_bbps_user_catalog_cache()
        return Response({'success': True, 'data': {'id': row.pk}, 'message': 'Biller deleted', 'errors': []}, status=200)
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
        for m in BbpsBillerMaster.objects.filter(is_deleted=False, biller_id__in=cleaned)
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
    master = BbpsBillerMaster.objects.filter(biller_id=bid, is_deleted=False).first()
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
    now = timezone.now()
    count = BbpsBillerMaster.objects.filter(is_deleted=False).count()
    BbpsBillerMaster.objects.filter(is_deleted=False).update(
        is_deleted=True,
        deleted_at=now,
        soft_deleted_at=now,
        is_active_local=False,
        updated_by_admin_at=now,
        updated_at=now,
    )
    _invalidate_bbps_user_catalog_cache()
    return Response(
        {
            'success': True,
            'data': {'cleared_count': count},
            'message': 'All billers removed from active database view',
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


def _sync_quota_snapshot():
    cfg = BillAvenueConfig.objects.filter(is_deleted=False, enabled=True, is_active=True).first()
    max_calls = int(getattr(cfg, 'mdm_max_calls_per_day', 15) or 15)
    today = timezone.localdate()
    row = BbpsSyncUsageLog.objects.filter(is_deleted=False, usage_date=today).first()
    used = int(getattr(row, 'call_count', 0) or 0)
    return {
        'usage_date': today,
        'max_calls_per_day': max_calls,
        'used_calls_today': used,
        'remaining_calls_today': max(0, max_calls - used),
        'last_sync_at': row.updated_at if row else None,
        'last_sync_result': str(getattr(row, 'last_status', '') or ''),
    }


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
    quota = _sync_quota_snapshot()
    if quota['remaining_calls_today'] <= 0:
        return Response(
            {
                'success': False,
                'data': quota,
                'message': 'Daily BBPS sync quota exhausted',
                'errors': [],
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    request_id = f"SYNC{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"
    usage_date = quota['usage_date']
    try:
        with transaction.atomic():
            usage, _ = BbpsSyncUsageLog.objects.select_for_update().get_or_create(
                usage_date=usage_date,
                is_deleted=False,
                defaults={
                    'call_count': 0,
                    'requested_ids_count': 0,
                    'requested_by': request.user if request.user and request.user.is_authenticated else None,
                    'request_id': request_id,
                },
            )
            if usage.call_count >= quota['max_calls_per_day']:
                q = _sync_quota_snapshot()
                return Response({'success': False, 'data': q, 'message': 'Daily BBPS sync quota exhausted', 'errors': []}, status=429)
            usage.call_count = F('call_count') + 1
            usage.requested_ids_count = F('requested_ids_count') + len(biller_ids)
            usage.requested_by = request.user if request.user and request.user.is_authenticated else None
            usage.request_id = request_id
            usage.last_status = 'started'
            usage.last_error = ''
            usage.meta = {'requested_ids': len(biller_ids)}
            usage.save(update_fields=['call_count', 'requested_ids_count', 'requested_by', 'request_id', 'last_status', 'last_error', 'meta', 'updated_at'])

        out = sync_biller_info(biller_ids, request_id=request_id)
        BbpsSyncUsageLog.objects.filter(is_deleted=False, usage_date=usage_date).update(last_status='success', meta={'requested_ids': len(biller_ids), 'synced': out.get('updated_count', 0)})
        _invalidate_bbps_user_catalog_cache()
        quota_out = _sync_quota_snapshot()
        out['quota'] = quota_out
        return Response({'success': True, 'data': out, 'message': 'Biller sync completed', 'errors': []}, status=200)
    except BillAvenueEntitlementError as e:
        BbpsSyncUsageLog.objects.filter(is_deleted=False, usage_date=usage_date).update(last_status='failed', last_error=str(e))
        logger.warning('sync-billers BillAvenue entitlement (205): %s', e)
        return Response(
            {
                'success': False,
                'data': {
                    'billavenue_code': '205',
                    'hint': (
                        'BillAvenue MDM entitlement/profile mismatch for this institute or agent. '
                        'Ask BillAvenue to confirm MDM access for your accessCode/instituteId/agentId and server egress IP.'
                    ),
                },
                'message': str(e),
                'errors': ['205'],
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except BillAvenueClientError as e:
        BbpsSyncUsageLog.objects.filter(is_deleted=False, usage_date=usage_date).update(last_status='failed', last_error=str(e))
        msg = str(e or '')
        code = ''
        if 'code=001' in msg:
            code = '001'
        elif 'code=205' in msg:
            code = '205'
        elif 'missing responsecode' in msg.lower() or 'missing responseCode' in msg:
            code = 'PARSE'
        if code:
            cached_count = BbpsBillerMaster.objects.filter(is_deleted=False).count()
            logger.info('sync-billers BillAvenue upstream code=%s (non-fatal when cache exists): %s', code, msg)
            hint = (
                'BillAvenue returned a malformed/partial MDM payload (missing responseCode). '
                'Existing synced catalog remains usable; retry sync later or verify upstream gateway response format.'
                if code == 'PARSE'
                else (
                    'BillAvenue blocked live MDM call for this config/agent at this moment. '
                    'Existing synced catalog remains usable; complete prerequisites and retry sync later.'
                )
            )
            return Response(
                {
                    'success': False,
                    'data': {
                        'billavenue_code': code,
                        'mdm_cached_count': cached_count,
                        'quota': _sync_quota_snapshot(),
                        'hint': hint,
                    },
                    'message': msg,
                    'errors': [],
                },
                status=200,
            )
        return Response({'success': False, 'data': None, 'message': msg, 'errors': []}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def sync_usage_today_view(request):
    return Response({'success': True, 'data': _sync_quota_snapshot(), 'message': 'Sync usage retrieved', 'errors': []}, status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def sync_usage_history_view(request):
    rows = BbpsSyncUsageLog.objects.filter(is_deleted=False).order_by('-usage_date')[:30]
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
        msg = str(exc)
        status_code = 409 if 'duplicate complaint' in msg.lower() else 400
        return Response({'success': False, 'data': None, 'message': msg, 'errors': []}, status=status_code)
    except BillAvenueClientError as exc:
        return Response({'success': False, 'data': None, 'message': _friendly_complaint_error_message(str(exc)), 'errors': []}, status=400)
    except BillAvenueTransportError as exc:
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
        return Response({'success': False, 'data': None, 'message': 'Complaint not found', 'errors': []}, status=404)
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
        for m in BbpsBillerMaster.objects.filter(is_deleted=False, biller_id__in=requested_ids)
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
