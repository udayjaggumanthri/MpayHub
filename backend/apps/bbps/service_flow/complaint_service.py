from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

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


def _is_complaint_existing_ticket_error(exc: Exception) -> bool:
    low = str(exc or '').lower()
    return 'code=001' in low and (
        'unable to raise' in low
        or 'already exist' in low
        or 'in-process' in low
        or 'in process' in low
        or 'ticket is already' in low
    )


def _is_complaint_unable_to_process_error(exc: Exception) -> bool:
    low = str(exc or '').lower()
    return 'code=001' in low and 'unable to process' in low


def _format_payment_anchor(attempt: BbpsPaymentAttempt | None) -> str:
    if not attempt:
        return ''
    anchor = getattr(attempt, 'settled_at', None) or getattr(attempt, 'created_at', None)
    if not anchor:
        return ''
    return timezone.localtime(anchor).strftime('%d %b %Y, %I:%M %p')


def _nearby_open_complaint_hints(*, user, upstream_txn_ref_id: str) -> str:
    """
    BillAvenue often rejects one CC… while a sibling txn (typo / repeat pay) already has a ticket.
    Suggest open complaints sharing the same txn prefix (last two chars differ).
    """
    base = str(upstream_txn_ref_id or '').strip()
    if len(base) < 14 or not base.upper().startswith('CC'):
        return ''
    prefix = base[:-2]
    hints: list[str] = []
    for row in (
        BbpsComplaint.objects.filter(
            user=user,
            is_deleted=False,
            txn_ref_id__startswith=prefix,
        )
        .exclude(txn_ref_id=base)
        .order_by('-created_at')[:4]
    ):
        if _is_terminal_complaint_status(row.complaint_status):
            continue
        hints.append(f'{row.txn_ref_id} → Complaint ID {row.complaint_id}')
    if not hints:
        return ''
    return (
        ' Nearby payment(s) on your account already have an open complaint: '
        + '; '.join(hints)
        + '. Use Complaint Management → Track complaint with that Complaint ID, or verify the CC… ID on your receipt.'
    )


def _raise_for_register_failure(
    *,
    user,
    upstream_txn_ref_id: str,
    attempt: BbpsPaymentAttempt | None,
    last_error: BillAvenueClientError,
) -> None:
    """Convert BillAvenue register failures into actionable TransactionFailed messages."""
    if _is_complaint_existing_ticket_error(last_error):
        existing_any = _find_any_open_complaint_for_txn(user=user, upstream_txn_ref_id=upstream_txn_ref_id)
        if existing_any:
            raise TransactionFailed(
                'BillAvenue reports this transaction already has an active complaint ticket. '
                f'Your open case in this portal: Complaint ID {existing_any.complaint_id} '
                f'(disposition: {existing_any.complaint_disposition}). '
                'Use Complaint Management → Track complaint and enter that Complaint ID.'
            ) from last_error
        raise TransactionFailed(
            'BillAvenue reports a complaint ticket may already exist for this transaction at the provider. '
            'Use Complaint Management → Track complaint with your B-Connect transaction ID, or contact support '
            'with the BillAvenue request ID from this screen.'
        ) from last_error

    if _is_complaint_unable_to_process_error(last_error):
        paid = _format_payment_anchor(attempt)
        paid_clause = f' Payment completed on {paid}.' if paid else ''
        existing_any = _find_any_open_complaint_for_txn(user=user, upstream_txn_ref_id=upstream_txn_ref_id)
        msg = (
            f'BillAvenue declined complaint registration for {upstream_txn_ref_id}.{paid_clause} '
            'The payment is successful in mPayHub, but the provider does not accept a new complaint for this '
            'exact transaction reference right now.'
        )
        if existing_any:
            msg += (
                f' You already have Complaint ID {existing_any.complaint_id} saved for this txn in mPayHub — '
                'use Track complaint with that ID.'
            )
        msg += _nearby_open_complaint_hints(user=user, upstream_txn_ref_id=upstream_txn_ref_id)
        msg += (
            ' If the CC… ID matches your receipt and this persists, email cms@billavenue.com with disposition, '
            'description, and the BillAvenue request ID shown below.'
        )
        raise TransactionFailed(msg) from last_error

    raise last_error


# BillAvenue official disposition strings (NPCI wording). UI may send legacy phrasing — normalize before upstream.
# viii) matches BillAvenue XML samples (no trailing period on the disposition line).
_BILLAVENUE_OFFICIAL_COMPLAINT_DISPOSITIONS: tuple[str, ...] = (
    'Transaction Successful, Amount Debited but services not received',
    'Transaction Successful, Amount Debited but Service Disconnected or Service Stopped',
    'Transaction Successful, Amount Debited but Late Payment Surcharge Charges add in next bill',
    'Erroneously paid in wrong account',
    'Duplicate Payment',
    'Erroneously paid the wrong amount',
    'Payment information not received from Biller or Delay in receiving payment information from the Biller.',
    'Bill Paid but Amount not adjusted or still showing due amount',
)
_DISPOSITION_BY_CASEFOLD: dict[str, str] = {s.casefold(): s for s in _BILLAVENUE_OFFICIAL_COMPLAINT_DISPOSITIONS}
# Older portal labels / casing → official string BillAvenue expects.
_LEGACY_COMPLAINT_DISPOSITION_ALIASES: dict[str, str] = {
    'transaction successful, amount debited but service disconnected or stopped': 'Transaction Successful, Amount Debited but Service Disconnected or Service Stopped',
    'transaction successful, amount debited but late payment surcharge charges added': 'Transaction Successful, Amount Debited but Late Payment Surcharge Charges add in next bill',
    'erroneously paid wrong amount': 'Erroneously paid the wrong amount',
    'payment info not received / delayed from biller': 'Payment information not received from Biller or Delay in receiving payment information from the Biller.',
    'bill paid but still showing due amount': 'Bill Paid but Amount not adjusted or still showing due amount',
    # Some docs show a trailing full stop on viii); wire XML samples often omit it.
    'bill paid but amount not adjusted or still showing due amount.': 'Bill Paid but Amount not adjusted or still showing due amount',
}


def _canonical_billavenue_complaint_disposition(value: str) -> str:
    raw = str(value or '').strip()
    if not raw:
        return raw
    k = raw.casefold()
    if k in _LEGACY_COMPLAINT_DISPOSITION_ALIASES:
        return _LEGACY_COMPLAINT_DISPOSITION_ALIASES[k]
    return _DISPOSITION_BY_CASEFOLD.get(k, raw)


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
        attempt = attempt or _find_attempt_for_upstream_txn(user=user, upstream_txn=raw)
        return raw, attempt

    return raw, None


def _find_attempt_for_upstream_txn(*, user, upstream_txn: str) -> BbpsPaymentAttempt | None:
    """Resolve local payment row for a B-Connect txn ref (ORM field or nested pay response)."""
    upstream_txn = str(upstream_txn or '').strip()
    if not upstream_txn:
        return None
    row = (
        BbpsPaymentAttempt.objects.filter(user=user, txn_ref_id=upstream_txn, is_deleted=False)
        .select_related('bill_payment')
        .order_by('-created_at')
        .first()
    )
    if row:
        return row
    for row in (
        BbpsPaymentAttempt.objects.filter(user=user, is_deleted=False, status='SUCCESS')
        .select_related('bill_payment')
        .order_by('-created_at')[:100]
    ):
        if _txn_ref_from_attempt_row(row) == upstream_txn:
            return row
    return None


def _complaint_max_payment_age_days() -> int:
    try:
        return max(1, int(getattr(settings, 'BBPS_COMPLAINT_MAX_PAYMENT_AGE_DAYS', 90)))
    except (TypeError, ValueError):
        return 90


def _validate_complaint_eligibility(*, attempt: BbpsPaymentAttempt | None, upstream_txn_ref_id: str) -> None:
    if not attempt:
        raise TransactionFailed(
            'No matching successful payment was found for this B-Connect transaction ID on your account. '
            'Open the payment under My Bills, copy the B-Connect transaction ID (CC…) from the receipt, then retry.'
        )
    st = str(getattr(attempt, 'status', '') or '').strip().upper()
    if st != 'SUCCESS':
        raise TransactionFailed(
            f'Complaints can only be registered for successful payments. This payment status is {st or "unknown"}.'
        )
    anchor = getattr(attempt, 'settled_at', None) or getattr(attempt, 'updated_at', None) or getattr(attempt, 'created_at', None)
    if anchor:
        age = timezone.now() - anchor
        max_days = _complaint_max_payment_age_days()
        if age.days > max_days:
            paid_on = timezone.localtime(anchor).strftime('%d-%b-%Y')
            raise TransactionFailed(
                f'This payment was completed on {paid_on} ({age.days} days ago). '
                f'BillAvenue may no longer accept new complaints for {upstream_txn_ref_id}. '
                'Use a recent payment from My Bills, or contact support with the BillAvenue request ID from your receipt.'
            )


def _preflight_billavenue_txn_visible(*, attempt: BbpsPaymentAttempt, upstream_txn_ref_id: str) -> None:
    """
    When BillAvenue cannot see the txn in transaction status, complaint register usually returns 001.
    Best-effort check only — does not block if the status API errors.
    """
    client = BBPSClient()
    anchor = getattr(attempt, 'settled_at', None) or getattr(attempt, 'created_at', None)
    from_d = ''
    to_d = ''
    if anchor:
        local = timezone.localtime(anchor)
        from_d = (local - timedelta(days=2)).strftime('%d/%m/%Y')
        to_d = (local + timedelta(days=2)).strftime('%d/%m/%Y')
    try:
        data = client.transaction_status(
            track_type='TRANS_REF_ID',
            track_value=upstream_txn_ref_id,
            from_date=from_d,
            to_date=to_d,
        )
    except Exception:
        return
    rows: list = []
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        inner = data.get('transactions') or data.get('txnList') or data.get('txnDetails')
        if isinstance(inner, list):
            rows = inner
        elif data.get('txnRefId') or data.get('txnReferenceId'):
            rows = [data]
    if not rows:
        raise TransactionFailed(
            f'BillAvenue could not find transaction {upstream_txn_ref_id} for complaint registration. '
            'Confirm the CC… ID from your latest My Bills receipt, ensure the payment shows as successful, '
            'and retry after a few minutes if you just paid.'
        )
    needle = upstream_txn_ref_id.strip().upper()
    for row in rows:
        if not isinstance(row, dict):
            continue
        ref = str(
            row.get('txnRefId')
            or row.get('txnReferenceId')
            or row.get('txn_ref_id')
            or row.get('txnReferenceID')
            or ''
        ).strip().upper()
        if ref == needle:
            return
    raise TransactionFailed(
        f'BillAvenue could not match transaction {upstream_txn_ref_id} in their records. '
        'Use the B-Connect transaction ID from the receipt of the payment you want to dispute.'
    )


def _billavenue_complaint_correlation_extras(attempt: BbpsPaymentAttempt | None) -> dict:
    """
    BillAvenue complaint register often correlates the case to the original bill-pay context.
    Without agent / biller / payment reference, UAT may return complaintResponseCode=001 and refuse
    the txnRefId even when the payment succeeded.
    """
    if not attempt:
        return {}
    out: dict = {}
    rp = attempt.request_payload if isinstance(attempt.request_payload, dict) else {}
    agent = str(rp.get('agent_id') or rp.get('agentId') or '').strip()
    if agent:
        out['agentId'] = agent
    biller = str(getattr(attempt, 'biller_id', '') or '').strip()
    if biller:
        out['billerId'] = biller
    pay_ref = str(getattr(attempt, 'request_id', '') or '').strip()
    if pay_ref:
        out['paymentRefId'] = pay_ref
    return out


def _find_open_duplicate_complaint(*, user, upstream_txn_ref_id: str, complaint_disposition: str):
    canon = str(complaint_disposition or '').strip()
    rows = (
        BbpsComplaint.objects.filter(
            user=user,
            is_deleted=False,
            txn_ref_id=upstream_txn_ref_id,
        )
        .order_by('-created_at')
    )
    for row in rows:
        if _is_terminal_complaint_status(row.complaint_status):
            continue
        if _canonical_billavenue_complaint_disposition(str(row.complaint_disposition or '')) == canon:
            return row
    return None


def _find_any_open_complaint_for_txn(*, user, upstream_txn_ref_id: str) -> BbpsComplaint | None:
    """First non-terminal complaint for this user + B-Connect txn (any disposition)."""
    rows = (
        BbpsComplaint.objects.filter(
            user=user,
            is_deleted=False,
            txn_ref_id=upstream_txn_ref_id,
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
    disposition = _canonical_billavenue_complaint_disposition(str(complaint_disposition or '').strip())
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
    _validate_complaint_eligibility(attempt=attempt, upstream_txn_ref_id=upstream_txn_ref_id)
    if attempt:
        _preflight_billavenue_txn_visible(attempt=attempt, upstream_txn_ref_id=upstream_txn_ref_id)
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
    other_open = _find_any_open_complaint_for_txn(user=user, upstream_txn_ref_id=upstream_txn_ref_id)
    if other_open and _canonical_billavenue_complaint_disposition(str(other_open.complaint_disposition or '')) != disposition:
        raise TransactionFailed(
            'This transaction already has an open complaint on your account '
            f'(Complaint ID {other_open.complaint_id}, disposition: {other_open.complaint_disposition}). '
            'BillAvenue usually rejects a second ticket until that case is closed. '
            'Use Complaint Management → Track complaint and enter that Complaint ID.'
        )
    enforce_complaint_cooling(attempt=attempt)
    # BillAvenue XML samples: txnRefId + complaintDesc + complaintDisposition (minimal). Try minimal first;
    # enriched agent/biller/paymentRefId helps some stacks but triggers 001 on others.
    core = {
        'txnRefId': upstream_txn_ref_id,
        'complaintDisposition': disposition,
    }
    extras = _billavenue_complaint_correlation_extras(attempt)
    payload_attempts = [
        {**core, 'complaintDesc': desc},
        *([{**core, 'complaintDesc': desc, **extras}] if extras else []),
        {**core, 'complainDesc': desc},
        {
            **core,
            'complaintDesc': desc,
            'complainDesc': desc,
            'complaintDescription': desc,
        },
        {**core, 'complaintType': 'Transaction', 'complaintDesc': desc},
        {**core, 'complaintType': 'Transaction', 'complaintDesc': desc, **extras},
        {**core, 'complaintDesc': desc, **extras},
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
            if not _is_description_missing_error(exc) and not (
                _is_complaint_existing_ticket_error(exc) or _is_complaint_unable_to_process_error(exc)
            ):
                raise
            if idx == len(payload_attempts) - 1 and not (
                _is_complaint_existing_ticket_error(exc) or _is_complaint_unable_to_process_error(exc)
            ):
                raise
    if resp is None and last_error:
        # Ensure support can correlate with BillAvenue logs even when the last raised error
        # did not carry requestId (e.g. chained retries).
        br = str(last_billavenue_request_id or '').strip()
        if br and not str(getattr(last_error, 'billavenue_request_id', '') or '').strip():
            setattr(last_error, 'billavenue_request_id', br)
        if last_error and (
            _is_complaint_existing_ticket_error(last_error)
            or _is_complaint_unable_to_process_error(last_error)
        ):
            _raise_for_register_failure(
                user=user,
                upstream_txn_ref_id=upstream_txn_ref_id,
                attempt=attempt,
                last_error=last_error,
            )
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
