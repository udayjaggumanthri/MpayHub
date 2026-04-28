from __future__ import annotations

from apps.bbps.models import BbpsDepositEnquirySnapshot
from apps.integrations.bbps_client import BBPSClient


def enquire_deposits(*, from_date: str, to_date: str, trans_type: str = '', agents: list[str] | None = None, request_id: str = '', transaction_id: str = '') -> dict:
    client = BBPSClient()
    payload = {
        'fromDate': from_date,
        'toDate': to_date,
        'transType': trans_type,
        'agents': agents or [],
        'requestId': request_id,
        'transactionId': transaction_id,
    }
    resp = client.enquire_deposits(payload)
    shot = BbpsDepositEnquirySnapshot.objects.create(
        request_id=request_id,
        from_date=from_date,
        to_date=to_date,
        trans_type=trans_type,
        current_balance=str(resp.get('currentBalance') or '0'),
        currency=str(resp.get('currency') or 'INR'),
        response_payload=resp,
    )
    return {'snapshot_id': shot.pk, 'response': resp}
