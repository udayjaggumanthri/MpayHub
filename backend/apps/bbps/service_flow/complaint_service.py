from __future__ import annotations

import uuid

from apps.bbps.models import BbpsComplaint, BbpsComplaintEvent, BbpsPaymentAttempt
from apps.bbps.service_flow.compliance import enforce_complaint_cooling
from apps.core.exceptions import TransactionFailed
from apps.integrations.billavenue.errors import BillAvenueClientError
from apps.integrations.bbps_client import BBPSClient


def _registration_row_from_response(resp: dict) -> dict:
    """
    BBPS / BillAvenue may return complaint registration under ``complaintRegistrationResp``
    or flat JSON; business outcome codes may appear as ``complaintResponseCode`` / ``complaintResponseReason``
    (per Bharat Bill Payment System 2.8.7 samples) or legacy ``responseCode`` / ``responseReason``.
    """
    r = resp if isinstance(resp, dict) else {}
    inner = r.get('complaintRegistrationResp')
    inner = inner if isinstance(inner, dict) else {}

    def pick(*keys: str) -> str:
        for m in (inner, r):
            if not isinstance(m, dict):
                continue
            for k in keys:
                v = m.get(k)
                if v is None:
                    continue
                s = str(v).strip()
                if s:
                    return s
        return ''

    return {
        'complaintId': pick('complaintId'),
        'complaintStatus': pick('complaintStatus') or 'ASSIGNED',
        'responseCode': pick('complaintResponseCode', 'responseCode'),
        'responseReason': pick('complaintResponseReason', 'responseReason'),
    }


def _tracking_row_from_response(resp: dict) -> dict:
    """Normalize complaint track body (wrapped or flat per BBPS 2.8.7 JSON samples)."""
    r = resp if isinstance(resp, dict) else {}
    inner = r.get('complaintTrackingResp')
    inner = inner if isinstance(inner, dict) else {}

    def pick(*keys: str) -> str:
        for m in (inner, r):
            if not isinstance(m, dict):
                continue
            for k in keys:
                v = m.get(k)
                if v is None:
                    continue
                s = str(v).strip()
                if s:
                    return s
        return ''

    return {
        'complaintAssigned': pick('complaintAssigned'),
        'complaintId': pick('complaintId'),
        'complaintStatus': pick('complaintStatus'),
        'complaintResponseCode': pick('complaintResponseCode', 'responseCode'),
        'complaintResponseReason': pick('complaintResponseReason', 'responseReason'),
        'complaintRemarks': pick('complaintRemarks', 'remarks'),
    }


def _normalize_track_api_response(resp: dict) -> dict:
    """Expose a stable ``complaintTrackingResp`` object whether upstream returned flat or nested JSON."""
    r = resp if isinstance(resp, dict) else {}
    if isinstance(r.get('complaintTrackingResp'), dict) and r.get('complaintTrackingResp'):
        return r
    row = _tracking_row_from_response(r)
    if any(str(row.get(k) or '').strip() for k in ('complaintId', 'complaintStatus', 'complaintResponseCode')):
        # BBPS 2.8.7 sample response is flat; normalize to the same shape clients already handle.
        return {'complaintTrackingResp': row}
    return r


def _is_description_missing_error(exc: Exception) -> bool:
    low = str(exc or '').lower()
    return 'v5004' in low or 'description missing' in low


def _is_manual_escalation_error(exc: Exception) -> bool:
    low = str(exc or '').lower()
    return 'e051' in low or 'cms@billavenue.com' in low or 'code=257' in low


def _is_terminal_complaint_status(status: str) -> bool:
    s = str(status or '').strip().upper()
    return s in {'RESOLVED', 'CLOSED', 'REJECTED', 'CANCELLED'}


def _find_open_duplicate_complaint(*, user, upstream_txn_ref_id: str, complaint_disposition: str):
    rows = (
        BbpsComplaint.objects.filter(
            user=user,
            is_deleted=False,
            txn_ref_id=upstream_txn_ref_id,
            complaint_disposition__iexact=complaint_disposition,
        )
        .order_by('-created_at')
    )
    for row in rows:
        if not _is_terminal_complaint_status(row.complaint_status):
            return row
    return None


def register_complaint(*, user, txn_ref_id: str, complaint_desc: str, complaint_disposition: str) -> BbpsComplaint:
    client = BBPSClient()
    raw_ref = str(txn_ref_id or '').strip()
    desc = str(complaint_desc or '').strip()
    disposition = str(complaint_disposition or '').strip()
    if not desc:
        raise TransactionFailed('Complaint description is required.')
    if not disposition:
        raise TransactionFailed('Complaint disposition is required.')
    attempt = BbpsPaymentAttempt.objects.filter(txn_ref_id=raw_ref, is_deleted=False).first()
    upstream_txn_ref_id = raw_ref
    # UI users often copy internal service ID (PMBBPS...) from My Bills table.
    # If we can map it to a settled attempt, use the true B-Connect txn_ref_id for complaints.
    if not attempt and raw_ref:
        attempt = BbpsPaymentAttempt.objects.filter(
            service_id=raw_ref,
            is_deleted=False,
        ).order_by('-created_at').first()
        if attempt and str(getattr(attempt, 'txn_ref_id', '') or '').strip():
            upstream_txn_ref_id = str(attempt.txn_ref_id).strip()
    if not upstream_txn_ref_id:
        raise TransactionFailed(
            'B-Connect Transaction ID is required. Use the transaction reference that starts with CC... from receipt/success screen.'
        )
    duplicate = _find_open_duplicate_complaint(
        user=user,
        upstream_txn_ref_id=upstream_txn_ref_id,
        complaint_disposition=disposition,
    )
    if duplicate:
        raise TransactionFailed(
            'Duplicate complaint already exists for this transaction and disposition. '
            f'Use Complaint ID {duplicate.complaint_id} to track the current case.'
        )
    enforce_complaint_cooling(attempt=attempt)
    # Bharat Bill Payment System 2.8.7 / BillAvenue UAT: minimal JSON is txnRefId + complaintDesc + complaintDisposition
    # (see postman_billavenue_uat_collection "Complaint Register (ver 2.0)"). Do not send disposition codes (D11, …).
    base_payload = {
        'txnRefId': upstream_txn_ref_id,
        'complaintDisposition': disposition,
    }
    payload_attempts = [
        {**base_payload, 'complaintDesc': desc},
        # BillAvenue v2.8.7 JSON sample uses complainDesc (without "t").
        {**base_payload, 'complainDesc': desc},
        # Some partner stacks accept one or more aliases.
        {
            **base_payload,
            'complaintDesc': desc,
            'complainDesc': desc,
            'complaintDescription': desc,
        },
        # Last resort: optional complaint classification used on some stacks (not in minimal Postman sample).
        {**base_payload, 'complaintDesc': desc, 'complaintType': 'Transaction'},
    ]
    resp = None
    last_error = None
    for idx, payload in enumerate(payload_attempts):
        try:
            resp = client.register_complaint(payload)
            last_error = None
            break
        except BillAvenueClientError as exc:
            last_error = exc
            if _is_manual_escalation_error(exc):
                manual_id = f"MANUAL-{uuid.uuid4().hex[:12].upper()}"
                return BbpsComplaint.objects.create(
                    user=user,
                    attempt=attempt,
                    txn_ref_id=upstream_txn_ref_id,
                    complaint_id=manual_id,
                    complaint_desc=desc,
                    complaint_disposition=disposition,
                    complaint_status='MANUAL_ESCALATION_REQUIRED',
                    response_code='257',
                    response_reason='Provider requested manual complaint escalation to cms@billavenue.com',
                    raw_payload={'provider_error': str(exc)},
                )
            if not _is_description_missing_error(exc):
                raise
            if idx == len(payload_attempts) - 1:
                raise
    if resp is None and last_error:
        raise last_error
    body = _registration_row_from_response(resp)
    c = BbpsComplaint.objects.create(
        user=user,
        attempt=attempt,
        txn_ref_id=upstream_txn_ref_id,
        complaint_id=str(body.get('complaintId') or ''),
        complaint_desc=desc,
        complaint_disposition=disposition,
        complaint_status=str(body.get('complaintStatus') or 'ASSIGNED'),
        response_code=str(body.get('responseCode') or ''),
        response_reason=str(body.get('responseReason') or '')[:100],
        raw_payload=resp,
    )
    return c


def track_complaint(*, complaint: BbpsComplaint) -> dict:
    if str(getattr(complaint, 'complaint_status', '') or '') == 'MANUAL_ESCALATION_REQUIRED':
        payload = {
            'complaintTrackingResp': {
                'complaintId': complaint.complaint_id,
                'complaintStatus': complaint.complaint_status,
                'complaintResponseCode': complaint.response_code or '257',
                'complaintResponseReason': complaint.response_reason or 'MANUAL_ESCALATION',
                'complaintRemarks': 'Manual escalation required: email cms@billavenue.com with transaction details.',
            }
        }
        BbpsComplaintEvent.objects.create(
            complaint=complaint,
            complaint_status=complaint.complaint_status,
            remarks='Manual escalation required: email cms@billavenue.com with transaction details.',
            response_payload=payload,
        )
        return payload
    client = BBPSClient()
    payload = {'complaintId': complaint.complaint_id}
    resp = client.track_complaint(payload)
    body = _tracking_row_from_response(resp)
    complaint.complaint_status = str(body.get('complaintStatus') or complaint.complaint_status)
    complaint.response_code = str(body.get('complaintResponseCode') or '')
    complaint.response_reason = str(body.get('complaintResponseReason') or '')[:100]
    complaint.raw_payload = resp
    complaint.save(update_fields=['complaint_status', 'response_code', 'response_reason', 'raw_payload', 'updated_at'])
    BbpsComplaintEvent.objects.create(
        complaint=complaint,
        complaint_status=complaint.complaint_status,
        remarks=str(body.get('complaintRemarks') or ''),
        response_payload=resp,
    )
    return _normalize_track_api_response(resp)
