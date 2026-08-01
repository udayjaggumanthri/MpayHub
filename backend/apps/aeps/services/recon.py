"""Mandatory Fingpay three-way recon + optional callbacks."""
from __future__ import annotations

import json

from apps.aeps.models import AepsReconBatch, AepsReconItem, AepsTransaction
from apps.integrations.fingpay.crypto import scrub_sensitive
from apps.integrations.fingpay.registry import get_fingpay_client


def handle_three_way_recon(*, raw_body: str, headers: dict, client_ip: str | None = None) -> dict:
    """
    Fingpay posts recon payload; we reply per txn with '00' (success) or 'Failed'.
    Hash: Base64(SHA256(requestbody + superMerchantLoginId + secretKey))
    """
    client = get_fingpay_client()
    provided_hash = (
        headers.get('hash')
        or headers.get('Hash')
        or headers.get('HTTP_HASH')
        or ''
    )
    if not client.verify_recon_hash(request_body=raw_body, provided_hash=str(provided_hash)):
        return {'status': False, 'message': 'Invalid hash', 'statusCode': 10001}

    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        payload = {}

    items_in = []
    if isinstance(payload, list):
        items_in = payload
    elif isinstance(payload, dict):
        items_in = payload.get('data') or payload.get('transactions') or payload.get('txnList') or []
        if isinstance(payload.get('merchantTransactionId'), str):
            items_in = [payload]

    batch = AepsReconBatch.objects.create(
        txn_date=str(headers.get('txnDate') or headers.get('TxnDate') or ''),
        request_hash=str(provided_hash)[:128],
        item_count=len(items_in) if isinstance(items_in, list) else 0,
        raw_request=scrub_sensitive(payload if isinstance(payload, (dict, list)) else {}),
        client_ip=client_ip,
    )

    replies = []
    if isinstance(items_in, list):
        for item in items_in:
            if not isinstance(item, dict):
                continue
            mid = str(
                item.get('merchantTransactionId')
                or item.get('merchantTranId')
                or item.get('merchantRefNo')
                or ''
            )
            fpid = str(item.get('fingpayTransactionId') or item.get('fpTransactionId') or '')
            txn = None
            if mid:
                txn = AepsTransaction.objects.filter(merchant_tran_id=mid, is_deleted=False).first()
            if not txn and fpid:
                txn = AepsTransaction.objects.filter(fp_transaction_id=fpid, is_deleted=False).first()

            if txn and txn.status in ('success', 'reconciled') and txn.response_code in ('00', '') and txn.bank_rrn:
                reply = '00'
                our_status = txn.status
                if txn.status == 'success':
                    txn.status = 'reconciled'
                    txn.save(update_fields=['status', 'updated_at'])
            else:
                reply = 'Failed'
                our_status = txn.status if txn else 'missing'

            AepsReconItem.objects.create(
                batch=batch,
                merchant_tran_id=mid,
                fp_transaction_id=fpid,
                our_status=our_status,
                reply_code=reply,
                matched_transaction=txn,
                details=scrub_sensitive(item),
            )
            replies.append(
                {
                    'merchantTransactionId': mid,
                    'fingpayTransactionId': fpid,
                    'status': reply,
                }
            )

    response = {'status': True, 'message': 'successful', 'data': replies, 'statusCode': 10000}
    batch.raw_response = response
    batch.item_count = len(replies)
    batch.save(update_fields=['raw_response', 'item_count'])
    return response


def handle_transaction_callback(*, payload: dict) -> dict:
    """Optional mobile callback updater."""
    payload = payload or {}
    mid = str(payload.get('merchantRefNo') or payload.get('merchantTranId') or '')
    if not mid:
        return {'ok': False, 'message': 'missing merchant ref'}
    txn = AepsTransaction.objects.filter(merchant_tran_id=mid, is_deleted=False).first()
    if not txn:
        return {'ok': False, 'message': 'txn not found'}
    status_flag = str(payload.get('transactionStatus') or '').upper()
    txn.fp_transaction_id = str(payload.get('fpTransactionId') or txn.fp_transaction_id)
    txn.bank_rrn = str(payload.get('bankRRN') or txn.bank_rrn)
    txn.response_message = str(payload.get('errorMessage') or txn.response_message)[:500]
    if status_flag == 'S':
        txn.status = 'success'
        txn.response_code = '00'
    elif status_flag == 'F':
        txn.status = 'failed'
    elif status_flag == 'I':
        txn.status = 'pending'
    txn.provider_meta = {**(txn.provider_meta or {}), 'callback': scrub_sensitive(payload)}
    txn.save()
    return {'ok': True, 'merchant_tran_id': mid, 'status': txn.status}
