"""
Merge BillAvenue transaction-status rows with local payment attempt data when available.
"""
from __future__ import annotations

from apps.bbps.models import BbpsPaymentAttempt
from apps.bbps.receipt_context import build_bill_payment_receipt_context, _extract_biller_response
from apps.integrations.bbps_client import extract_biller_response_dict


def _scalar(value) -> str:
    if value is None:
        return ''
    s = str(value).strip()
    return s


def _merge_txn_dict(base: dict, extra: dict) -> dict:
    out = dict(base or {})
    for key, value in (extra or {}).items():
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            existing = out.get(key)
            if not existing:
                out[key] = value
            elif isinstance(existing, dict) and isinstance(value, dict):
                merged = dict(existing)
                merged.update(value)
                out[key] = merged
            continue
        existing = out.get(key)
        if existing is None or _scalar(existing) == '':
            out[key] = value
    return out


def _amount_display(payment) -> str:
    if not payment:
        return ''
    try:
        return str(payment.amount)
    except Exception:
        return ''


def local_snapshot_from_attempt(attempt: BbpsPaymentAttempt) -> dict:
    payment = getattr(attempt, 'bill_payment', None)
    payload = attempt.request_payload if isinstance(attempt.request_payload, dict) else {}
    br = _extract_biller_response(payload) or extract_biller_response_dict(payload) or {}
    ctx = build_bill_payment_receipt_context(payment) if payment else {}

    mobile = (
        _scalar(payload.get('mobile'))
        or _scalar(payload.get('mobileNumber'))
        or _scalar(payload.get('customerMobile'))
        or _pick_br_scalar(br, 'mobileNumber', 'mobileNo', 'customerMobile')
    )
    biller_name = ctx.get('biller_name') or ''
    biller_id = _scalar(getattr(payment, 'biller_id', '')) if payment else ''
    amount = _amount_display(payment)
    ccf = ''
    if payment:
        try:
            ccf = str(getattr(payment, 'service_charge', None) or getattr(payment, 'charge', None) or '')
        except Exception:
            ccf = ''
    if not ccf:
        try:
            ccf = str(getattr(attempt, 'ccf_amount', '') or '')
        except Exception:
            pass

    txn_status = _scalar(attempt.status)
    if payment and not txn_status:
        txn_status = _scalar(payment.status)

    out = {
        'txnReferenceId': _scalar(attempt.txn_ref_id),
        'txnRefId': _scalar(attempt.txn_ref_id),
        'requestId': _scalar(attempt.request_id),
        'serviceId': _scalar(attempt.service_id),
        'billerName': biller_name or biller_id,
        'billerId': biller_id,
        'mobileNumber': mobile,
        'registeredMobile': mobile,
        'billNumber': ctx.get('bill_number') or '',
        'billDate': ctx.get('bill_date') or '',
        'dueDate': ctx.get('due_date') or '',
        'billPeriod': ctx.get('bill_period') or '',
        'paymentMode': ctx.get('payment_mode') or _scalar(attempt.payment_mode),
        'initChannel': ctx.get('init_channel') or _scalar(attempt.payment_channel),
        'customerName': ctx.get('customer_name') or '',
        'customerConvenienceFee': ccf,
        'ccf': ccf,
        'convFee': ccf,
        'billAmount': amount,
        'totalAmount': amount,
        'amount': amount,
        'txnStatus': txn_status,
        'txnDate': attempt.created_at.isoformat() if attempt.created_at else '',
        'transactionDateTime': attempt.created_at.isoformat() if attempt.created_at else '',
        'approvalRefNumber': _scalar(getattr(attempt, 'approval_ref_number', '')),
        'billType': _scalar(getattr(payment, 'bill_type', '')) if payment else '',
        'category': _scalar(getattr(payment, 'bill_type', '')) if payment else '',
        'receipt_details': ctx,
        'customer_details': payload.get('customer_details') if isinstance(payload.get('customer_details'), dict) else {},
        'input_params': payload.get('input_params') if isinstance(payload.get('input_params'), list) else [],
        'billerResponse': br,
        '_enrichedFromLocal': True,
    }
    return {k: v for k, v in out.items() if v not in (None, '', {}, [])}


def _pick_br_scalar(br: dict, *keys: str) -> str:
    for key in keys:
        val = br.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ''


def enrich_transactions_for_query(user, txns: list) -> list:
    if not isinstance(txns, list):
        return txns
    out = []
    for row in txns:
        if not isinstance(row, dict):
            out.append(row)
            continue
        enriched = dict(row)
        ref = _scalar(
            row.get('txnReferenceId')
            or row.get('txnRefId')
            or row.get('txn_ref_id')
        )
        if ref and user:
            attempt = (
                BbpsPaymentAttempt.objects.filter(
                    user=user, txn_ref_id=ref, is_deleted=False
                )
                .select_related('bill_payment')
                .order_by('-created_at')
                .first()
            )
            if attempt:
                enriched = _merge_txn_dict(enriched, local_snapshot_from_attempt(attempt))
        out.append(enriched)
    return out
