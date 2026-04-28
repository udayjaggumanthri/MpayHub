from __future__ import annotations

from apps.bbps.models import BbpsBillerMaster, BbpsFetchSession
from apps.bbps.service_flow.compliance import validate_channel_device_fields
from apps.integrations.bbps_client import BBPSClient


def fetch_bill_with_cache(*, user, biller_id: str, customer_info: dict, input_params: list, agent_device_info: dict, agent_id: str = '', biller_adhoc: bool = False) -> dict:
    client = BBPSClient()
    master = BbpsBillerMaster.objects.filter(biller_id=biller_id, is_deleted=False).first()
    init_channel = str((agent_device_info or {}).get('initChannel') or '')
    validate_channel_device_fields(init_channel=init_channel, agent_device_info=agent_device_info or {})
    result = client.fetch_bill(
        biller_id,
        (master.biller_category if master else ''),
        customerInfo=customer_info,
        input=input_params,
        agentDeviceInfo=agent_device_info,
        agent_id=agent_id,
        biller_adhoc=biller_adhoc,
    )

    session = BbpsFetchSession.objects.create(
        user=user,
        biller_master=master,
        request_id=str(result.get('request_id') or ''),
        service_id=str(result.get('request_id') or ''),
        input_params={'input': input_params, 'customerInfo': customer_info, 'agentDeviceInfo': agent_device_info},
        biller_response=result.get('raw') or {},
        amount_paise=int(float(result.get('amount') or 0) * 100),
        raw_response=result.get('raw') or {},
        status='FETCHED',
    )
    return {'fetch_session': session, 'bill_result': result}
