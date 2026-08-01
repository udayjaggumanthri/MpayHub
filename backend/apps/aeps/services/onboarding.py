"""Merchant onboarding + eKYC orchestration."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.aeps.models import AepsApiAuditLog, AepsTransaction
from apps.aeps.services.gates import assert_entitled, get_merchant
from apps.aeps.services.ids import generate_merchant_tran_id, merchant_pin_plain
from apps.integrations.fingpay.crypto import mask_aadhaar, md5_hex, scrub_sensitive
from apps.integrations.fingpay.registry import get_fingpay_client


def save_onboarding_draft(*, user, payload: dict) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing. Contact Admin to re-enable AEPS.'})
    if merchant.stage == 'active':
        raise ValidationError({'message': 'Merchant already active.'})
    cleaned = scrub_sensitive(payload or {})
    # Keep masked aadhaar if provided
    aadhaar = str((payload or {}).get('aadhaarNumber') or (payload or {}).get('aadhaar') or '')
    if aadhaar:
        merchant.masked_aadhaar = mask_aadhaar(aadhaar)
        cleaned['aadhaarNumber'] = merchant.masked_aadhaar
    merchant.onboarding_payload = {**(merchant.onboarding_payload or {}), **cleaned}
    if merchant.stage == 'not_started':
        merchant.stage = 'onboarding_draft'
    merchant.save()
    return {'stage': merchant.stage, 'onboarding_payload': merchant.onboarding_payload}


@transaction.atomic
def submit_onboarding(*, user, latitude, longitude, ip_address: str, merchant_body: dict | None = None) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})

    body = merchant_body or (merchant.onboarding_payload or {})
    # Inject login credentials for Fingpay
    pin = merchant_pin_plain(merchant)
    fingpay_merchant = {
        **body,
        'merchantLoginId': merchant.merchant_login_id,
        'merchantLoginPin': md5_hex(pin) if pin else body.get('merchantLoginPin'),
    }
    # Restore full aadhaar only from request body if caller sent it (not from stored draft)
    if merchant_body and merchant_body.get('aadhaarNumber'):
        fingpay_merchant['aadhaarNumber'] = merchant_body['aadhaarNumber']
        merchant.masked_aadhaar = mask_aadhaar(merchant_body['aadhaarNumber'])

    client = get_fingpay_client()
    txn = AepsTransaction.objects.create(
        user=user,
        merchant=merchant,
        merchant_tran_id=generate_merchant_tran_id('ONB'),
        product='ONB',
        status='pending',
        latitude=latitude,
        longitude=longitude,
        client_ip=ip_address or None,
        device_imei=merchant.device_imei or '',
        masked_aadhaar=merchant.masked_aadhaar,
    )
    try:
        resp = client.create_merchant(
            fingpay_merchant,
            latitude=latitude,
            longitude=longitude,
            ip_address=ip_address or '0.0.0.0',
        )
    except Exception as exc:
        txn.status = 'failed'
        txn.response_message = str(exc)[:500]
        txn.save(update_fields=['status', 'response_message', 'updated_at'])
        merchant.last_error = str(exc)[:1000]
        merchant.save(update_fields=['last_error', 'updated_at'])
        AepsApiAuditLog.objects.create(
            endpoint='onboarding/create',
            merchant_tran_id=txn.merchant_tran_id,
            user=user,
            success=False,
            error_message=str(exc)[:500],
            request_summary=scrub_sensitive({'merchantLoginId': merchant.merchant_login_id}),
        )
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc

    ok = bool(resp.get('status') is True or resp.get('statusCode') in (10000, '10000'))
    txn.status = 'success' if ok else 'failed'
    txn.response_code = str(resp.get('statusCode') or '')
    txn.response_message = str(resp.get('message') or '')[:500]
    txn.provider_meta = scrub_sensitive(resp)
    txn.fp_transaction_id = str((resp.get('data') or {}).get('encodeFPTxnId') or resp.get('encodeFPTxnId') or '')
    txn.save()

    AepsApiAuditLog.objects.create(
        endpoint='onboarding/create',
        merchant_tran_id=txn.merchant_tran_id,
        user=user,
        success=ok,
        provider_status_code=txn.response_code,
        latency_ms=(resp.get('_meta') or {}).get('latency_ms'),
        request_summary=scrub_sensitive({'merchantLoginId': merchant.merchant_login_id}),
        response_summary=scrub_sensitive({'status': resp.get('status'), 'statusCode': resp.get('statusCode'), 'message': resp.get('message')}),
    )

    if ok:
        merchant.stage = 'ekyc_pending'
        merchant.fingpay_onboarding_ref = txn.fp_transaction_id or txn.merchant_tran_id
        merchant.onboarding_payload = scrub_sensitive({**(merchant.onboarding_payload or {}), **(merchant_body or {})})
        merchant.last_latitude = latitude
        merchant.last_longitude = longitude
        merchant.last_error = ''
        merchant.save()
    else:
        merchant.last_error = txn.response_message
        merchant.save(update_fields=['last_error', 'updated_at'])
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': txn.response_message or 'Onboarding failed'})

    return {'transaction': _txn_dict(txn), 'merchant_stage': merchant.stage}


def ekyc_start(*, user, payload: dict, device_imei: str, latitude, longitude) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    client = get_fingpay_client()
    body = {
        'superMerchantId': int(client.super_merchant_id) if str(client.super_merchant_id).isdigit() else client.super_merchant_id,
        'merchantLoginId': merchant.merchant_login_id,
        'transactionType': 'EKY',
        'mobileNumber': payload.get('mobileNumber') or getattr(user, 'phone', ''),
        'aadharNumber': payload.get('aadhaarNumber') or payload.get('aadharNumber'),
        'panNumber': payload.get('panNumber'),
        'matmSerialNumber': payload.get('matmSerialNumber') or '',
        'latitude': float(latitude),
        'longitude': float(longitude),
    }
    if body['aadharNumber']:
        merchant.masked_aadhaar = mask_aadhaar(body['aadharNumber'])
    txn = AepsTransaction.objects.create(
        user=user,
        merchant=merchant,
        merchant_tran_id=generate_merchant_tran_id('EKY'),
        product='EKY',
        status='pending',
        latitude=latitude,
        longitude=longitude,
        device_imei=device_imei or merchant.device_imei,
        masked_aadhaar=merchant.masked_aadhaar,
    )
    try:
        resp = client.ekyc_post('fpekyc/api/ekyc/merchant/php/sendotp', body, device_imei=device_imei or merchant.device_imei)
    except Exception as exc:
        txn.status = 'failed'
        txn.response_message = str(exc)[:500]
        txn.save()
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc

    data = resp.get('data') or {}
    merchant.ekyc_primary_key_id = str(data.get('primaryKeyId') or '')
    merchant.ekyc_encode_fp_txn_id = str(data.get('encodeFPTxnId') or '')
    merchant.stage = 'ekyc_pending'
    merchant.device_imei = device_imei or merchant.device_imei
    merchant.save()
    txn.fp_transaction_id = merchant.ekyc_encode_fp_txn_id
    txn.provider_meta = scrub_sensitive(resp)
    txn.response_code = str(resp.get('statusCode') or '')
    txn.response_message = str(resp.get('message') or '')[:500]
    txn.status = 'pending'
    txn.save()
    return {
        'transaction': _txn_dict(txn),
        'primaryKeyId': merchant.ekyc_primary_key_id,
        'encodeFPTxnId': merchant.ekyc_encode_fp_txn_id,
    }


def ekyc_verify_otp(*, user, otp: str) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    client = get_fingpay_client()
    body = {
        'superMerchantId': int(client.super_merchant_id) if str(client.super_merchant_id).isdigit() else client.super_merchant_id,
        'merchantLoginId': merchant.merchant_login_id,
        'otp': otp,
        'primaryKeyId': int(merchant.ekyc_primary_key_id) if str(merchant.ekyc_primary_key_id).isdigit() else merchant.ekyc_primary_key_id,
        'encodeFPTxnId': merchant.ekyc_encode_fp_txn_id,
    }
    resp = client.ekyc_post('fpekyc/api/ekyc/merchant/php/validateotp', body, device_imei=merchant.device_imei)
    return scrub_sensitive(resp)


def ekyc_biometric(*, user, capture_response: dict, latitude, longitude) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    client = get_fingpay_client()
    body = {
        'superMerchantId': int(client.super_merchant_id) if str(client.super_merchant_id).isdigit() else client.super_merchant_id,
        'merchantLoginId': merchant.merchant_login_id,
        'primaryKeyId': int(merchant.ekyc_primary_key_id) if str(merchant.ekyc_primary_key_id).isdigit() else merchant.ekyc_primary_key_id,
        'encodeFPTxnId': merchant.ekyc_encode_fp_txn_id,
        'captureResponse': capture_response,
        'latitude': float(latitude),
        'longitude': float(longitude),
    }
    # Pass captureResponse through unchanged
    try:
        resp = client.ekyc_post('fpekyc/api/ekyc/merchant/php/biometric', body, device_imei=merchant.device_imei)
    except Exception as exc:
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc

    ok = bool(resp.get('status') is True or str(resp.get('statusCode')) == '10000')
    data = resp.get('data') or {}
    kyc_code = str(data.get('kycResponseCode') or data.get('responseCode') or '')
    if ok and kyc_code in ('0', '00', ''):
        merchant.stage = 'active'
        merchant.activated_at = timezone.now()
        merchant.fingpay_ekyc_ref = str(data.get('fingpayTransactionId') or '')
        merchant.last_error = ''
        merchant.save()
    else:
        merchant.last_error = str(resp.get('message') or data.get('responseMessage') or 'eKYC failed')[:1000]
        merchant.save(update_fields=['last_error', 'updated_at'])

    txn = AepsTransaction.objects.filter(user=user, product='EKY').order_by('-created_at').first()
    if txn:
        txn.status = 'success' if merchant.stage == 'active' else 'failed'
        txn.response_code = kyc_code or str(resp.get('statusCode') or '')
        txn.response_message = str(resp.get('message') or data.get('responseMessage') or '')[:500]
        txn.fp_transaction_id = str(data.get('fingpayTransactionId') or txn.fp_transaction_id)
        txn.bank_rrn = str(data.get('rrn') or '')
        txn.provider_meta = scrub_sensitive(resp)
        txn.save()

    AepsApiAuditLog.objects.create(
        endpoint='ekyc/biometric',
        merchant_tran_id=txn.merchant_tran_id if txn else '',
        user=user,
        success=merchant.stage == 'active',
        response_summary=scrub_sensitive({'status': resp.get('status'), 'statusCode': resp.get('statusCode')}),
    )
    if merchant.stage != 'active':
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': merchant.last_error or 'eKYC failed'})
    return {'merchant_stage': merchant.stage, 'transaction': _txn_dict(txn) if txn else None}


def register_device(*, user, device_imei: str) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    serial = (device_imei or '').strip()
    if not serial:
        raise ValidationError({'message': 'Mantra device serial is required.'})
    merchant.device_imei = serial
    merchant.device_ready = True
    merchant.save(update_fields=['device_imei', 'device_ready', 'updated_at'])
    return {'device_imei': merchant.device_imei, 'device_ready': True}


def _txn_dict(txn: AepsTransaction | None) -> dict | None:
    if not txn:
        return None
    return {
        'id': txn.pk,
        'merchant_tran_id': txn.merchant_tran_id,
        'product': txn.product,
        'status': txn.status,
        'amount': str(txn.amount),
        'bank_rrn': txn.bank_rrn,
        'fp_transaction_id': txn.fp_transaction_id,
        'response_code': txn.response_code,
        'response_message': txn.response_message,
        'masked_aadhaar': txn.masked_aadhaar,
        'created_at': txn.created_at.isoformat() if txn.created_at else None,
    }
