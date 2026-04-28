from __future__ import annotations

from django.utils import timezone

from apps.bbps.models import BbpsPaymentAttempt, BbpsStatusPollLog
from apps.bbps.service_flow.compliance import enforce_awaited_poll_cooling
from apps.integrations.bbps_client import BBPSClient


STATUS_MAP = {
    'SUCCESS': 'SUCCESS',
    'FAILURE': 'FAILED',
    'FAILED': 'FAILED',
    'REFUND': 'REFUNDED',
    'REFUNDED': 'REFUNDED',
}


def _extract_txn_status(payload: dict) -> str:
    if not payload:
        return ''
    if payload.get('txnStatus'):
        return str(payload.get('txnStatus'))
    if isinstance(payload.get('txnList'), list) and payload['txnList']:
        return str(payload['txnList'][0].get('txnStatus') or '')
    node = payload.get('transactionStatusResp') or {}
    if isinstance(node.get('txnList'), list) and node['txnList']:
        return str(node['txnList'][0].get('txnStatus') or '')
    return ''


def poll_attempt_status(attempt: BbpsPaymentAttempt) -> BbpsPaymentAttempt:
    enforce_awaited_poll_cooling(attempt=attempt, minimum_minutes=15)
    client = BBPSClient()
    track_type = 'REQUEST_ID' if attempt.request_id else 'TRANS_REF_ID'
    track_value = attempt.request_id or attempt.txn_ref_id
    payload = client.transaction_status(track_type=track_type, track_value=track_value)
    txn_status = _extract_txn_status(payload).upper()

    BbpsStatusPollLog.objects.create(
        attempt=attempt,
        track_type=track_type,
        track_value=track_value,
        response_code=str(payload.get('responseCode') or ''),
        txn_status=txn_status,
        response_payload=payload,
    )

    mapped = STATUS_MAP.get(txn_status)
    if mapped:
        attempt.status = mapped
        if mapped in ('SUCCESS', 'FAILED', 'REFUNDED', 'REVERSED'):
            attempt.settled_at = timezone.now()
        attempt.save(update_fields=['status', 'settled_at', 'updated_at'])
        if attempt.bill_payment:
            if mapped == 'SUCCESS':
                attempt.bill_payment.status = 'SUCCESS'
                attempt.bill_payment.save(update_fields=['status'])
            elif mapped in ('FAILED', 'REFUNDED', 'REVERSED'):
                attempt.bill_payment.status = 'FAILED'
                if mapped in ('REFUNDED', 'REVERSED'):
                    attempt.bill_payment.failure_reason = f'Status changed to {mapped}'
                attempt.bill_payment.save(update_fields=['status', 'failure_reason'])
    return attempt
