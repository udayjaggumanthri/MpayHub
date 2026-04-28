from __future__ import annotations

from apps.bbps.models import BbpsBillerInputParam, BbpsBillerMaster
from apps.core.exceptions import TransactionFailed
from apps.integrations.bbps_client import BBPSClient


def validate_biller_inputs(*, biller_id: str, input_map: dict) -> None:
    required = BbpsBillerInputParam.objects.filter(
        biller__biller_id=biller_id,
        is_optional=False,
        is_deleted=False,
        biller__is_deleted=False,
    )
    missing = []
    for p in required:
        val = input_map.get(p.param_name)
        if val in (None, ''):
            missing.append(p.param_name)
    if missing:
        raise TransactionFailed(f'Missing required biller input(s): {", ".join(missing)}')


def validate_bill_account(*, biller_id: str, agent_id: str, input_params: list) -> dict:
    biller = BbpsBillerMaster.objects.filter(biller_id=biller_id, is_deleted=False).first()
    flag = (biller.biller_support_bill_validation if biller else '')
    if str(flag).upper() == 'NOT_SUPPORTED':
        return {'skipped': True, 'reason': 'validation_not_supported'}

    client = BBPSClient()
    payload = {'agentId': agent_id, 'billerId': biller_id, 'inputParams': {'input': input_params}}
    normalized = client.validate_bill(payload)
    resp_code = str(normalized.get('responseCode') or normalized.get('billValidationResponse', {}).get('responseCode') or '000')
    if resp_code not in ('000', '0') and str(flag).upper() == 'MANDATORY':
        raise TransactionFailed(f'Bill validation failed for biller={biller_id}')
    return {'response': normalized, 'response_code': resp_code}
