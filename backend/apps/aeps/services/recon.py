"""Mandatory Fingpay three-way recon + optional callbacks."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from django.utils import timezone

from apps.aeps.models import AepsReconBatch, AepsReconItem, AepsTransaction
from apps.integrations.fingpay.crypto import build_recon_hash, scrub_sensitive
from apps.integrations.fingpay.registry import get_fingpay_client


def handle_three_way_recon(*, raw_body: str, headers: dict, client_ip: str | None = None) -> dict:
    """
    Inbound: Fingpay posts recon payload; we reply per txn with '00' (success) or 'Failed'.
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
        direction='inbound',
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


def _service_type_for_product(product: str) -> str:
    p = str(product or '').upper()
    if p == 'AP':
        return 'M'
    if p in ('CW', 'CD', 'CD_OTP', 'BE', 'MS'):
        return 'CW' if p in ('CW', 'BE', 'MS') else 'CW'
    return p or 'CW'


def build_recon_items(for_date: date | None = None) -> list[dict]:
    """Build outbound recon payload items for a calendar day (local)."""
    day = for_date or timezone.localdate()
    start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
    end = start + timedelta(days=1)
    qs = AepsTransaction.objects.filter(
        is_deleted=False,
        product__in=('CW', 'AP', 'CD', 'CD_OTP'),
        created_at__gte=start,
        created_at__lt=end,
    ).exclude(status='initiated').order_by('id')
    items = []
    for txn in qs:
        if txn.status in ('success', 'reconciled') and txn.bank_rrn and txn.response_code in ('00', ''):
            code = '00'
        else:
            code = str(txn.response_code or 'Failed') or 'Failed'
            if code == '00' and not txn.bank_rrn:
                code = 'Failed'
        items.append(
            {
                'merchantTransactionId': txn.merchant_tran_id,
                'fingpayTransactionId': txn.fp_transaction_id or '',
                'transactionRrn': txn.bank_rrn or '',
                'responseCode': code if code != '00' or txn.bank_rrn else 'Failed',
                'transactionDate': day.strftime('%d-%m-%Y'),
                'serviceType': 'M' if txn.product == 'AP' else 'CW',
            }
        )
    return items


def run_outbound_recon(*, txn_date: str | None = None, actor=None) -> dict:
    """
    POST recon items to Fingpay fpcollectservice (mandatory go-live).
    Chunks at 10_000 per docs.
    """
    client = get_fingpay_client()
    if txn_date:
        try:
            # Accept YYYY-MM-DD or DD-MM-YYYY
            raw = str(txn_date).strip()
            if '-' in raw and len(raw.split('-')[0]) == 4:
                day = datetime.strptime(raw[:10], '%Y-%m-%d').date()
            else:
                day = datetime.strptime(raw[:10], '%d-%m-%Y').date()
        except ValueError as exc:
            raise ValueError(f'Invalid txn_date: {txn_date}') from exc
    else:
        day = timezone.localdate() - timedelta(days=1)

    items = build_recon_items(day)
    header_date = day.strftime('%d/%m/%Y %H:%M:%S')
    batches_out = []
    chunk_size = 10000
    for i in range(0, max(len(items), 1), chunk_size):
        chunk = items[i : i + chunk_size]
        body_str = json.dumps(chunk, separators=(',', ':'), ensure_ascii=False)
        if not chunk:
            body_str = '[]'
        resp = client.push_three_way_recon(items=chunk, txn_date=header_date, body_json=body_str)
        batch = AepsReconBatch.objects.create(
            txn_date=header_date,
            direction='outbound',
            request_hash=str((resp or {}).get('_request_hash') or '')[:128],
            item_count=len(chunk),
            raw_request=scrub_sensitive(chunk),
            raw_response=scrub_sensitive(resp or {}),
            triggered_by=actor if getattr(actor, 'pk', None) else None,
        )
        data_rows = (resp or {}).get('data') if isinstance((resp or {}).get('data'), list) else []
        by_mid = {
            str(r.get('merchantTransactionId') or ''): r
            for r in data_rows
            if isinstance(r, dict)
        }
        for item in chunk:
            mid = item['merchantTransactionId']
            reply = by_mid.get(mid) or {}
            reply_code = str(reply.get('responseCode') or item.get('responseCode') or '')
            txn = AepsTransaction.objects.filter(merchant_tran_id=mid, is_deleted=False).first()
            if txn and reply_code == '00' and txn.status == 'success':
                txn.status = 'reconciled'
                txn.save(update_fields=['status', 'updated_at'])
            AepsReconItem.objects.create(
                batch=batch,
                merchant_tran_id=mid,
                fp_transaction_id=item.get('fingpayTransactionId') or '',
                our_status=txn.status if txn else 'missing',
                reply_code=reply_code or item.get('responseCode') or '',
                matched_transaction=txn,
                details=scrub_sensitive(reply or item),
            )
        batches_out.append(
            {
                'batch_id': batch.pk,
                'item_count': len(chunk),
                'apiStatus': (resp or {}).get('apiStatus'),
                'apiStatusMessage': (resp or {}).get('apiStatusMessage') or (resp or {}).get('message'),
            }
        )
        if not items:
            break

    return {
        'txn_date': day.isoformat(),
        'total_items': len(items),
        'batches': batches_out,
    }
