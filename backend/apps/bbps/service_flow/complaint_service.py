from __future__ import annotations

import uuid

from apps.bbps.models import BillPayment, BbpsComplaint, BbpsComplaintEvent, BbpsPaymentAttempt
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


def _is_internal_service_id(value: str) -> bool:
    return str(value or '').strip().upper().startswith('PMBBPS')


def _deep_find_txn_ref_in_payload(obj, *, depth: int = 0, max_depth: int = 12) -> str:
    """
    Recover B-Connect txnRefId from nested bill-pay / status JSON when the ORM field was not persisted.
    Ignores values that look like our internal PMBBPS service_id.
    """
    if depth > max_depth:
        return ''
    if isinstance(obj, dict):
        for key, val in obj.items():
            lk = str(key or '')
            if lk.lower() in ('txnrefid', 'txn_ref_id', 'txnref_id'):
                if isinstance(val, (str, int)):
                    cand = str(val).strip()
                    if cand and not _is_internal_service_id(cand):
                        return cand
            hit = _deep_find_txn_ref_in_payload(val, depth=depth + 1, max_depth=max_depth)
            if hit:
                return hit
    elif isinstance(obj, list):
        for item in obj[:80]:
            hit = _deep_find_txn_ref_in_payload(item, depth=depth + 1, max_depth=max_depth)
            if hit:
                return hit
    return ''


def _txn_ref_from_attempt_row(attempt: BbpsPaymentAttempt | None) -> str:
    if not attempt:
        return ''
    tid = str(getattr(attempt, 'txn_ref_id', '') or '').strip()
    if tid and not _is_internal_service_id(tid):
        return tid
    payload = getattr(attempt, 'response_payload', None)
    if isinstance(payload, dict):
        nested = _deep_find_txn_ref_in_payload(payload)
        if nested:
            return nested
    return ''


def _best_txn_ref_from_payment_attempts(*, user, bill_payment_id: int) -> tuple[str, BbpsPaymentAttempt | None]:
    """Prefer latest attempt with a non-empty upstream txn ref for this bill payment."""
    rows = (
        BbpsPaymentAttempt.objects.filter(
            user=user,
            bill_payment_id=bill_payment_id,
            is_deleted=False,
        )
        .order_by('-created_at')[:20]
    )
    for row in rows:
        tid = _txn_ref_from_attempt_row(row)
        if tid and not _is_internal_service_id(tid):
            return tid, row
    return '', None


def _resolve_complaint_txn_and_attempt(*, user, raw_ref: str) -> tuple[str, BbpsPaymentAttempt | None]:
    """
    Map user input (CC…, PMBBPS…, or bill-pay request_id) to the BillAvenue B-Connect txn ref and owning attempt.
    All ORM lookups are scoped to ``user`` so one user cannot resolve another user's payments.
    """
    raw = str(raw_ref or '').strip()
    if not raw:
        return '', None

    attempt = (
        BbpsPaymentAttempt.objects.filter(user=user, txn_ref_id=raw, is_deleted=False)
        .order_by('-created_at')
        .first()
    )
    if attempt:
        tid = (_txn_ref_from_attempt_row(attempt) or '').strip() or (raw if not _is_internal_service_id(raw) else '')
        if tid and not _is_internal_service_id(tid):
            return tid, attempt

    if _is_internal_service_id(raw):
        attempt = (
            BbpsPaymentAttempt.objects.filter(user=user, service_id=raw, is_deleted=False)
            .order_by('-created_at')
            .first()
        )
        if not attempt:
            bp = (
                BillPayment.objects.filter(user=user, service_id=raw, is_deleted=False)
                .order_by('-created_at')
                .first()
            )
            if bp:
                tid, att = _best_txn_ref_from_payment_attempts(user=user, bill_payment_id=bp.pk)
                if tid:
                    return tid, att
                attempt = (
                    BbpsPaymentAttempt.objects.filter(user=user, bill_payment_id=bp.pk, is_deleted=False)
                    .order_by('-created_at')
                    .first()
                )
        if attempt:
            tid = _txn_ref_from_attempt_row(attempt)
            if tid and not _is_internal_service_id(tid):
                return tid, attempt
            if attempt.bill_payment_id:
                tid, att = _best_txn_ref_from_payment_attempts(user=user, bill_payment_id=attempt.bill_payment_id)
                if tid:
                    return tid, att
        return raw, attempt

    attempt = (
        BbpsPaymentAttempt.objects.filter(user=user, request_id=raw, is_deleted=False)
        .order_by('-created_at')
        .first()
    )
    if attempt:
        tid = _txn_ref_from_attempt_row(attempt)
        if tid and not _is_internal_service_id(tid):
            return tid, attempt
        if attempt.bill_payment_id:
            tid, att = _best_txn_ref_from_payment_attempts(user=user, bill_payment_id=attempt.bill_payment_id)
            if tid:
                return tid, att

    if raw.upper().startswith('CC'):
        return raw, None

    return raw, None


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
    upstream_txn_ref_id, attempt = _resolve_complaint_txn_and_attempt(user=user, raw_ref=raw_ref)
    if not upstream_txn_ref_id:
        raise TransactionFailed(
            'B-Connect Transaction ID is required. Use the transaction reference that starts with CC... from receipt/success screen.'
        )
    if _is_internal_service_id(upstream_txn_ref_id):
        raise TransactionFailed(
            'Could not resolve this payment to a B-Connect transaction reference (CC…). '
            'Use the CC… value from your payment receipt or success screen, or the B-Connect txn shown after '
            'querying the transaction. Internal service IDs (PMBBPS…) cannot be sent to BillAvenue until the '
            'CC reference is available on the payment record.'
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
    last_billavenue_request_id = ''
    for idx, payload in enumerate(payload_attempts):
        try:
            normalized, rid = client.register_complaint(payload)
            last_billavenue_request_id = str(rid or '').strip() or last_billavenue_request_id
            resp = normalized
            last_error = None
            break
        except BillAvenueClientError as exc:
            last_error = exc
            rid = str(getattr(exc, 'billavenue_request_id', '') or '').strip()
            if rid:
                last_billavenue_request_id = rid
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
                    billavenue_request_id=last_billavenue_request_id,
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
        billavenue_request_id=last_billavenue_request_id,
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
