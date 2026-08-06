from __future__ import annotations

import uuid

from apps.bbps.catalog.env import get_biller_master
from apps.bbps.models import BbpsFetchSession
from apps.bbps.service_flow.compliance import validate_channel_device_fields
from apps.bbps.service_flow.validation_service import validate_bill_account
from apps.integrations.bbps_client import BBPSClient
from apps.integrations.billavenue.errors import BillAvenueTransportError


def _normalize_fetch_requirement(value: str | None) -> str:
    return str(value or '').strip().upper().replace('-', '_').replace(' ', '_')


def _fetch_not_supported(requirement: str) -> bool:
    req = _normalize_fetch_requirement(requirement)
    if not req:
        return False
    if req in ('NOT_SUPPORTED', 'UNSUPPORTED', 'QUICKPAY', 'QUICKPAY_ONLY', 'OPTIONAL_QUICKPAY'):
        return True
    return 'QUICKPAY' in req and ('ONLY' in req or 'NOT_SUPPORTED' in req)


def fetch_bill_with_cache(
    *,
    user,
    biller_id: str,
    customer_info: dict,
    input_params: list,
    agent_device_info: dict,
    agent_id: str = '',
    biller_adhoc: bool = False,
    plan_id: str = '',
) -> dict:
    master = get_biller_master(biller_id)
    init_channel = str((agent_device_info or {}).get('initChannel') or '')
    validate_channel_device_fields(init_channel=init_channel, agent_device_info=agent_device_info or {})
    input_rows = input_params if isinstance(input_params, list) else []
    fetch_req = _normalize_fetch_requirement(getattr(master, 'biller_fetch_requirement', '') if master else '')
    adhoc = bool(biller_adhoc or (getattr(master, 'biller_adhoc', False) if master else False))
    selected_plan_id = str(plan_id or '').strip()

    # MDM: billerFetchRequiremet=NOT_SUPPORTED → never call bill_fetch (PROD returns UM001 Invalid XML).
    # Use bill_validate when configured, then allow adhoc/custom amount payment.
    if _fetch_not_supported(fetch_req):
        validation = validate_bill_account(
            biller_id=biller_id,
            agent_id=agent_id,
            input_params=input_rows,
            customer_info=customer_info or {},
            agent_device_info=agent_device_info or {},
            plan_id=selected_plan_id,
        )
        request_id = f"VAL{uuid.uuid4().hex[:24].upper()}"
        raw = validation.get('response') if isinstance(validation, dict) else {}
        if not isinstance(raw, dict):
            raw = {'validation': validation}
        result = {
            'amount': 0,
            'due_date': '',
            'bill_date': '',
            'bill_number': 'ADHOC',
            'customer_name': '',
            'minimum_due': '0',
            'total_due': '0',
            'customer_details': {
                'customerInfo': customer_info,
                'input': input_rows,
                'agentDeviceInfo': agent_device_info,
                'planId': selected_plan_id,
            },
            'raw': raw,
            'request_id': request_id,
            'response_code': str((validation or {}).get('response_code') or '000'),
            'additional_info': [],
            'flow': 'adhoc_validate' if not validation.get('skipped') else 'adhoc',
            'fetch_requirement': fetch_req or 'NOT_SUPPORTED',
            'biller_adhoc': True,
            'validation_skipped': bool(validation.get('skipped')),
            'plan_id': selected_plan_id,
        }
        session = BbpsFetchSession.objects.create(
            user=user,
            biller_master=master,
            request_id=request_id,
            service_id=request_id,
            input_params={
                'input': input_rows,
                'customerInfo': customer_info,
                'agentDeviceInfo': agent_device_info,
                'planId': selected_plan_id,
            },
            biller_response=raw,
            additional_info=[],
            amount_paise=0,
            raw_response=raw,
            status='FETCHED',
        )
        return {'fetch_session': session, 'bill_result': result}

    client = BBPSClient()
    fetch_kwargs = {
        'customerInfo': customer_info,
        'input': input_rows,
        'agentDeviceInfo': agent_device_info,
        'agent_id': agent_id,
        'biller_adhoc': adhoc,
    }
    try:
        result = client.fetch_bill(
            biller_id,
            (master.biller_category if master else ''),
            **fetch_kwargs,
        )
    except BillAvenueTransportError as exc:
        # Upstream fetch can intermittently timeout for some billers; retry once before surfacing 503.
        if 'TIMEOUT' not in str(exc).upper():
            raise
        result = client.fetch_bill(
            biller_id,
            (master.biller_category if master else ''),
            **fetch_kwargs,
        )

    addl = result.get('additional_info') or []
    if not isinstance(addl, list):
        addl = []
    if selected_plan_id and isinstance(result, dict):
        result['plan_id'] = selected_plan_id
    session = BbpsFetchSession.objects.create(
        user=user,
        biller_master=master,
        request_id=str(result.get('request_id') or ''),
        service_id=str(result.get('request_id') or ''),
        input_params={
            'input': input_rows,
            'customerInfo': customer_info,
            'agentDeviceInfo': agent_device_info,
            'planId': selected_plan_id,
        },
        biller_response=result.get('raw') or {},
        additional_info=addl,
        amount_paise=int(float(result.get('amount') or 0) * 100),
        raw_response=result.get('raw') or {},
        status='FETCHED',
    )
    return {'fetch_session': session, 'bill_result': result}
