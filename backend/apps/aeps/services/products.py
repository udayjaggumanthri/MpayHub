"""AEPS product flows: 2FA, BE, MS, CW, AP, CD + status mid-points / ack."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.aeps.models import AepsApiAuditLog, AepsBankIinCache, AepsDaily2FA, AepsTransaction
from apps.aeps.services.gates import (
    assert_daily_2fa,
    assert_device_ready,
    assert_merchant_active,
)
from apps.aeps.services.ids import generate_merchant_tran_id, merchant_pin_plain
from apps.integrations.fingpay.crypto import mask_aadhaar, md5_hex, scrub_sensitive, trn_timestamp_now
from apps.integrations.fingpay.registry import get_active_provider, get_fingpay_client

# Product txn paths (aeps_base_url + path) — PHP per Fingpay Services API Doc
PATH_CW = 'fpaepsservice/api/cashWithdrawal/merchant/php/withdrawal'
PATH_BE = 'fpaepsservice/api/balanceInquiry/merchant/php/getBalance'
PATH_MS = 'fpaepsservice/api/miniStatement/merchant/php/statement'
PATH_AP = 'fpaepsservice/api/aadhaarPay/merchant/php/pay'
PATH_CD = 'fpaepsservice/api/CashDeposit/merchant/php/deposit'
PATH_CD_OTP_GENERATE = 'fpaepsservice/api/CashDeposit/merchant/php/generate/otp'
PATH_CD_OTP_VALIDATE = 'fpaepsservice/api/CashDeposit/merchant/php/validate/otp'
PATH_CD_OTP_TXN = 'fpaepsservice/api/CashDeposit/merchant/php/transaction'

# Daily 2FA — Two Factor Authentication Biometric 2.1
PATH_2FA = 'fpaepsservice/auth/tfauth/merchant/php/validate/aadhar'

# Acknowledgements (aeps host)
ACK_CW = 'fpaepsservice/api/cashWithdrawal/merchant/php/acknowledgement'
ACK_CD = 'fpaepsservice/api/CashDeposit/merchant/deposit/acknowledgement'
ACK_CD_OTP = 'fpaepsservice/api/CashDeposit/otp/merchant/acknowledgement'

# Status mid-points live on onboarding host (fpaepsweb), not fpaepsservice
STATUS_PATHS = {
    'CW': 'api/auth/merchantInfo/statusCheckV2/merchantLoginId/cashWithdrawal/v2',
    'CD': 'api/auth/merchantInfo/statusCheckV2/merchantLoginId/cashDeposit',
    'CD_OTP': 'api/auth/merchantInfo/statusCheck/cashDepositWithOtp',
    'AP': 'api/auth/merchantInfo/statusCheckV3/aadhaarPay/merchantLoginId',
    # BE/MS/2FA/ONB: fall back to CW-style mid-point when needed
    'BE': 'api/auth/merchantInfo/statusCheckV2/merchantLoginId/cashWithdrawal/v2',
    'MS': 'api/auth/merchantInfo/statusCheckV2/merchantLoginId/cashWithdrawal/v2',
}

ACK_PATHS = {
    'CW': ACK_CW,
    'AP': ACK_CW,  # Aadhaar Pay uses CW-style ack in practice when success
    'CD': ACK_CD,
    'CD_OTP': ACK_CD_OTP,
}


def status_path_for_product(product: str, *, otp_mode: bool = False) -> str:
    if otp_mode or product == 'CD_OTP':
        return STATUS_PATHS['CD_OTP']
    return STATUS_PATHS.get(product, STATUS_PATHS['CW'])


def ack_path_for_product(product: str, *, otp_mode: bool = False) -> str:
    if otp_mode or product == 'CD_OTP':
        return ACK_PATHS['CD_OTP']
    return ACK_PATHS.get(product, ACK_CW)


def _is_success(resp: dict, data: dict | None = None) -> bool:
    data = data or (resp.get('data') if isinstance(resp.get('data'), dict) else {}) or {}
    code = str(data.get('responseCode') or data.get('bankResponseCode') or '')
    rrn = str(data.get('bankRRN') or data.get('bankRrn') or data.get('rrn') or '')
    if code == '00' and rrn:
        return True
    if str(data.get('transactionStatusCode') or '') == 'FP009':
        return False
    api_ok = bool(resp.get('status') is True or str(resp.get('statusCode')) == '10000')
    if api_ok and code in ('00', '91', '52', '08') and rrn:
        return True
    return False


def _base_merchant_fields(merchant, client) -> dict:
    pin = merchant_pin_plain(merchant)
    return {
        'merchantUserName': merchant.merchant_login_id,
        'merchantPin': md5_hex(pin) if pin else '',
        'superMerchantId': str(client.super_merchant_id),
        'languageCode': 'en',
        'paymentType': 'B',
        'timestamp': trn_timestamp_now(),
    }


@transaction.atomic
def complete_daily_2fa(*, user, capture_response: dict, latitude, longitude, payload: dict | None = None) -> dict:
    merchant = assert_merchant_active(user)
    assert_device_ready(merchant)
    client = get_fingpay_client()
    today = timezone.localdate()
    row, _ = AepsDaily2FA.objects.get_or_create(merchant=merchant, for_date=today, defaults={'status': 'pending'})
    payload = payload or {}
    body = {
        **_base_merchant_fields(merchant, client),
        'captureResponse': capture_response,
        'latitude': float(latitude),
        'longitude': float(longitude),
        'transactionType': '2FA',
        'merchantTranId': generate_merchant_tran_id('2FA'),
        'mobileNumber': payload.get('mobileNumber') or '',
        'cardnumberORUID': payload.get('cardnumberORUID')
        or {
            'adhaarNumber': payload.get('aadhaarNumber') or payload.get('adhaarNumber') or '',
            'indicatorforUID': payload.get('indicatorforUID', 0),
            'nationalBankIdentificationNumber': payload.get('nationalBankIdentificationNumber')
            or payload.get('iin')
            or '',
        },
    }
    txn = AepsTransaction.objects.create(
        user=user,
        merchant=merchant,
        merchant_tran_id=body['merchantTranId'],
        product='2FA',
        status='pending',
        latitude=latitude,
        longitude=longitude,
        device_imei=merchant.device_imei,
        masked_aadhaar=mask_aadhaar(
            (body.get('cardnumberORUID') or {}).get('adhaarNumber') or ''
        ),
        bank_iin=str((body.get('cardnumberORUID') or {}).get('nationalBankIdentificationNumber') or ''),
    )
    try:
        resp = client.aeps_post(PATH_2FA, body, device_imei=merchant.device_imei)
    except Exception as exc:
        txn.status = 'failed'
        txn.response_message = str(exc)[:500]
        txn.save()
        row.status = 'failed'
        row.message = str(exc)[:500]
        row.save()
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc

    data = resp.get('data') if isinstance(resp.get('data'), dict) else {}
    ok = bool(resp.get('status') is True or str(resp.get('statusCode')) == '10000')
    txn.status = 'success' if ok else 'failed'
    txn.response_code = str((data or {}).get('responseCode') or resp.get('statusCode') or '')
    txn.response_message = str(resp.get('message') or '')[:500]
    txn.provider_meta = scrub_sensitive(resp)
    txn.save()
    row.status = 'success' if ok else 'failed'
    row.response_code = txn.response_code
    row.message = txn.response_message
    row.fingpay_ref = str((data or {}).get('fpTransactionId') or '')
    row.completed_at = timezone.now() if ok else None
    row.save()
    if ok:
        merchant.last_2fa_at = timezone.now()
        merchant.save(update_fields=['last_2fa_at', 'updated_at'])
    else:
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': txn.response_message or '2FA failed'})
    return {'twofa': {'date': str(today), 'status': row.status}, 'transaction_id': txn.merchant_tran_id}


def _create_pending_txn(*, user, merchant, product, amount, payload, latitude, longitude, ip) -> AepsTransaction:
    aadhaar = payload.get('aadhaarNumber') or payload.get('adhaarNumber') or ''
    return AepsTransaction.objects.create(
        user=user,
        merchant=merchant,
        merchant_tran_id=generate_merchant_tran_id(product),
        product=product,
        status='initiated',
        amount=Decimal(str(payload.get('transactionAmount') or payload.get('amount') or amount or 0)),
        bank_iin=str(payload.get('nationalBankIdentificationNumber') or payload.get('iin') or ''),
        bank_name=str(payload.get('bankName') or ''),
        masked_aadhaar=mask_aadhaar(aadhaar),
        customer_mobile=str(payload.get('mobileNumber') or ''),
        latitude=latitude,
        longitude=longitude,
        device_imei=merchant.device_imei,
        client_ip=ip or None,
    )


def _run_product(
    *,
    user,
    product: str,
    path: str,
    payload: dict,
    latitude,
    longitude,
    ip: str,
    require_2fa: bool,
    capture_response: dict,
) -> dict:
    merchant = assert_merchant_active(user)
    assert_device_ready(merchant)
    if require_2fa:
        assert_daily_2fa(merchant)
    client = get_fingpay_client()

    amount = payload.get('transactionAmount') or payload.get('amount') or 0
    if product in ('CW', 'AP', 'CD'):
        try:
            amt = float(amount)
        except (TypeError, ValueError) as exc:
            raise ValidationError({'message': 'Invalid amount'}) from exc
        if amt <= 0 or amt > 10000:
            raise ValidationError({'message': 'Amount must be between 1 and 10000'})

    txn = _create_pending_txn(
        user=user,
        merchant=merchant,
        product=product,
        amount=amount,
        payload=payload,
        latitude=latitude,
        longitude=longitude,
        ip=ip,
    )

    card = payload.get('cardnumberORUID') or {
        'adhaarNumber': payload.get('aadhaarNumber') or payload.get('adhaarNumber'),
        'indicatorforUID': payload.get('indicatorforUID', 0),
        'nationalBankIdentificationNumber': payload.get('nationalBankIdentificationNumber') or payload.get('iin'),
    }
    if payload.get('virtualId'):
        card['virtualId'] = payload['virtualId']

    body = {
        **_base_merchant_fields(merchant, client),
        'cardnumberORUID': card,
        'mobileNumber': payload.get('mobileNumber') or '',
        'transactionType': {'CW': 'CW', 'BE': 'BE', 'MS': 'MS', 'AP': 'M', 'CD': 'CD'}.get(product, product),
        'latitude': float(latitude),
        'longitude': float(longitude),
        'requestRemarks': payload.get('requestRemarks') or '',
        'captureResponse': capture_response,
        'transactionAmount': float(amount or 0),
    }
    if product == 'BE':
        body['merchantTransactionId'] = txn.merchant_tran_id
    else:
        body['merchantTranId'] = txn.merchant_tran_id

    txn.status = 'pending'
    txn.save(update_fields=['status', 'updated_at'])

    try:
        resp = client.aeps_post(path, body, device_imei=merchant.device_imei)
    except Exception as exc:
        txn.status = 'timeout'
        txn.response_message = str(exc)[:500]
        txn.save()
        AepsApiAuditLog.objects.create(
            endpoint=path,
            merchant_tran_id=txn.merchant_tran_id,
            user=user,
            success=False,
            error_message=str(exc)[:500],
        )
        return {'transaction': serialize_txn(txn), 'needs_status_check': True, 'error': str(exc)}

    data = resp.get('data') if isinstance(resp.get('data'), dict) else {}
    apply_provider_result(txn, resp, data)
    AepsApiAuditLog.objects.create(
        endpoint=path,
        merchant_tran_id=txn.merchant_tran_id,
        user=user,
        success=txn.status == 'success',
        provider_status_code=txn.response_code,
        latency_ms=(resp.get('_meta') or {}).get('latency_ms'),
        response_summary=scrub_sensitive(
            {'status': resp.get('status'), 'statusCode': resp.get('statusCode'), 'responseCode': txn.response_code}
        ),
    )
    if txn.status == 'success':
        try:
            acknowledge_transaction(txn)
        except Exception:
            pass
    return {'transaction': serialize_txn(txn), 'needs_status_check': txn.status == 'pending'}


def apply_provider_result(txn: AepsTransaction, resp: dict, data: dict) -> None:
    txn.response_code = str(data.get('responseCode') or '')
    txn.response_message = str(
        data.get('responseMessage') or data.get('errorMessage') or resp.get('message') or ''
    )[:500]
    txn.fp_transaction_id = str(
        data.get('fpTransactionId') or data.get('fingpayTransactionId') or data.get('fpTxnId') or ''
    )
    txn.bank_rrn = str(data.get('bankRRN') or data.get('bankRrn') or data.get('rrn') or '')
    if data.get('bankName'):
        txn.bank_name = str(data.get('bankName'))[:120]
    bal = data.get('balanceAmount') or data.get('bankAccountBalance')
    if bal is not None:
        try:
            txn.balance_amount = Decimal(str(bal))
        except Exception:
            pass
    if isinstance(data.get('miniStatement'), list):
        txn.mini_statement = data.get('miniStatement')
    elif isinstance(data.get('statement'), list):
        txn.mini_statement = data.get('statement')
    txn.provider_meta = scrub_sensitive(resp)

    if _is_success(resp, data):
        txn.status = 'success'
    elif str(data.get('transactionStatusCode') or '') == 'FP009' or str(resp.get('statusCode')) in ('', 'None'):
        txn.status = 'pending'
    elif txn.response_code in ('91', '52', '08') and not txn.bank_rrn:
        txn.status = 'pending'
    else:
        txn.status = 'failed'
    txn.save()


def acknowledge_transaction(txn: AepsTransaction, *, otp_mode: bool = False) -> None:
    if txn.acknowledged or txn.status != 'success':
        return
    client = get_fingpay_client()
    path = ack_path_for_product(txn.product, otp_mode=otp_mode)
    body = {
        'merchantTransactionId': txn.merchant_tran_id,
        'fingpayTransactionId': txn.fp_transaction_id,
        'acknowledgementStatus': True,
        'rrn': txn.bank_rrn,
        'responseCode': txn.response_code or '00',
    }
    try:
        client.aeps_post(path, body, device_imei=txn.device_imei or 'UNKNOWN')
    except Exception:
        pass
    txn.acknowledged = True
    txn.acknowledged_at = timezone.now()
    txn.save(update_fields=['acknowledged', 'acknowledged_at', 'updated_at'])


def status_check(*, user, merchant_tran_id: str, otp_mode: bool = False) -> dict:
    merchant = assert_merchant_active(user)
    try:
        txn = AepsTransaction.objects.get(user=user, merchant_tran_id=merchant_tran_id, is_deleted=False)
    except AepsTransaction.DoesNotExist as exc:
        raise ValidationError({'message': 'Transaction not found'}) from exc
    client = get_fingpay_client()
    path = status_path_for_product(txn.product, otp_mode=otp_mode)
    body = {
        **_base_merchant_fields(merchant, client),
        'merchantTranId': txn.merchant_tran_id,
        'merchantTransactionId': txn.merchant_tran_id,
        'transactionType': txn.product,
        'fingpayTransactionId': txn.fp_transaction_id or '',
    }
    try:
        resp = client.onboarding_post(path, body, device_imei=merchant.device_imei)
    except Exception as exc:
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc
    data = resp.get('data') if isinstance(resp.get('data'), dict) else {}
    apply_provider_result(txn, resp, data)
    if txn.status == 'success':
        acknowledge_transaction(txn, otp_mode=otp_mode or txn.product == 'CD_OTP')
    return {'transaction': serialize_txn(txn), 'status_path': path}


def cash_withdrawal(**kwargs):
    return _run_product(product='CW', path=PATH_CW, require_2fa=True, **kwargs)


def balance_enquiry(**kwargs):
    return _run_product(product='BE', path=PATH_BE, require_2fa=False, **kwargs)


def mini_statement(**kwargs):
    return _run_product(product='MS', path=PATH_MS, require_2fa=False, **kwargs)


def aadhaar_pay(**kwargs):
    return _run_product(product='AP', path=PATH_AP, require_2fa=True, **kwargs)


def cash_deposit(**kwargs):
    return _run_product(product='CD', path=PATH_CD, require_2fa=True, **kwargs)


def cash_deposit_otp_generate(*, user, payload: dict, latitude, longitude, ip: str) -> dict:
    """CD OTP step 1 — generate OTP (no biometric)."""
    merchant = assert_merchant_active(user)
    assert_device_ready(merchant)
    assert_daily_2fa(merchant)
    client = get_fingpay_client()
    amount = payload.get('transactionAmount') or payload.get('amount') or 0
    try:
        amt = float(amount)
    except (TypeError, ValueError) as exc:
        raise ValidationError({'message': 'Invalid amount'}) from exc
    if amt <= 0 or amt > 10000:
        raise ValidationError({'message': 'Amount must be between 1 and 10000'})

    txn = _create_pending_txn(
        user=user,
        merchant=merchant,
        product='CD',
        amount=amount,
        payload=payload,
        latitude=latitude,
        longitude=longitude,
        ip=ip,
    )
    card = payload.get('cardnumberORUID') or {
        'adhaarNumber': payload.get('aadhaarNumber') or payload.get('adhaarNumber'),
        'indicatorforUID': payload.get('indicatorforUID', 0),
        'nationalBankIdentificationNumber': payload.get('nationalBankIdentificationNumber') or payload.get('iin'),
    }
    body = {
        **_base_merchant_fields(merchant, client),
        'cardnumberORUID': card,
        'mobileNumber': payload.get('mobileNumber') or '',
        'transactionType': 'CD',
        'latitude': float(latitude),
        'longitude': float(longitude),
        'merchantTranId': txn.merchant_tran_id,
        'transactionAmount': float(amt),
    }
    txn.status = 'pending'
    meta = {'cd_otp_mode': True, 'cd_otp_step': 'generate'}
    txn.provider_meta = meta
    txn.save(update_fields=['status', 'provider_meta', 'updated_at'])
    try:
        resp = client.aeps_post(PATH_CD_OTP_GENERATE, body, device_imei=merchant.device_imei)
    except Exception as exc:
        txn.status = 'failed'
        txn.response_message = str(exc)[:500]
        txn.save()
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc
    data = resp.get('data') if isinstance(resp.get('data'), dict) else {}
    ok = bool(resp.get('status') is True or str(resp.get('statusCode')) == '10000')
    txn.fp_transaction_id = str(
        data.get('fpTransactionId') or data.get('fingpayTransactionId') or data.get('txnId') or ''
    )
    txn.response_message = str(resp.get('message') or '')[:500]
    txn.provider_meta = {**meta, 'generate_response': scrub_sensitive(resp), 'cd_otp_step': 'otp_sent' if ok else 'generate_failed'}
    txn.save()
    if not ok:
        txn.status = 'failed'
        txn.save(update_fields=['status', 'updated_at'])
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': txn.response_message or 'OTP generate failed'})
    return {'transaction': serialize_txn(txn), 'otp_sent': True}


def cash_deposit_otp_validate(*, user, merchant_tran_id: str, otp: str) -> dict:
    merchant = assert_merchant_active(user)
    try:
        txn = AepsTransaction.objects.get(user=user, merchant_tran_id=merchant_tran_id, product='CD', is_deleted=False)
    except AepsTransaction.DoesNotExist as exc:
        raise ValidationError({'message': 'Transaction not found'}) from exc
    client = get_fingpay_client()
    body = {
        **_base_merchant_fields(merchant, client),
        'merchantTranId': txn.merchant_tran_id,
        'otp': str(otp or '').strip(),
        'fingpayTransactionId': txn.fp_transaction_id or '',
    }
    try:
        resp = client.aeps_post(PATH_CD_OTP_VALIDATE, body, device_imei=merchant.device_imei)
    except Exception as exc:
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc
    ok = bool(resp.get('status') is True or str(resp.get('statusCode')) == '10000')
    meta = dict(txn.provider_meta or {})
    meta['cd_otp_step'] = 'otp_validated' if ok else 'otp_invalid'
    meta['validate_response'] = scrub_sensitive(resp)
    txn.provider_meta = meta
    txn.response_message = str(resp.get('message') or '')[:500]
    txn.save()
    if not ok:
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': txn.response_message or 'OTP invalid'})
    return {'transaction': serialize_txn(txn), 'otp_validated': True}


def cash_deposit_otp_submit(*, user, merchant_tran_id: str, latitude, longitude) -> dict:
    """CD OTP final transaction after OTP validated."""
    merchant = assert_merchant_active(user)
    assert_daily_2fa(merchant)
    try:
        txn = AepsTransaction.objects.get(user=user, merchant_tran_id=merchant_tran_id, product='CD', is_deleted=False)
    except AepsTransaction.DoesNotExist as exc:
        raise ValidationError({'message': 'Transaction not found'}) from exc
    meta = dict(txn.provider_meta or {})
    if meta.get('cd_otp_step') != 'otp_validated':
        raise ValidationError({'message': 'Validate OTP before submitting the deposit transaction'})
    client = get_fingpay_client()
    body = {
        **_base_merchant_fields(merchant, client),
        'merchantTranId': txn.merchant_tran_id,
        'fingpayTransactionId': txn.fp_transaction_id or '',
        'transactionType': 'CD',
        'latitude': float(latitude),
        'longitude': float(longitude),
        'transactionAmount': float(txn.amount or 0),
        'mobileNumber': txn.customer_mobile or '',
    }
    try:
        resp = client.aeps_post(PATH_CD_OTP_TXN, body, device_imei=merchant.device_imei)
    except Exception as exc:
        txn.status = 'timeout'
        txn.response_message = str(exc)[:500]
        txn.save()
        return {'transaction': serialize_txn(txn), 'needs_status_check': True, 'error': str(exc)}
    data = resp.get('data') if isinstance(resp.get('data'), dict) else {}
    apply_provider_result(txn, resp, data)
    meta = dict(txn.provider_meta or {})
    meta['cd_otp_mode'] = True
    meta['cd_otp_step'] = 'completed'
    txn.provider_meta = meta
    txn.save(update_fields=['provider_meta', 'updated_at'])
    if txn.status == 'success':
        acknowledge_transaction(txn, otp_mode=True)
    return {'transaction': serialize_txn(txn), 'needs_status_check': txn.status == 'pending'}


def sync_bank_iin_cache() -> int:
    provider = get_active_provider()
    client = get_fingpay_client()
    count = 0
    pairs = [
        ('aeps', provider.bank_list_url or f'{provider.aeps_base_url.rstrip("/")}/fpaepsservice/api/bankdata/bank/details'),
        (
            'aadhaar_pay',
            provider.aadhaar_pay_bank_list_url
            or f'{provider.aeps_base_url.rstrip("/")}/fpaepsservice/api/bankdata/bank/aadharpay',
        ),
    ]
    for list_type, url in pairs:
        if not url:
            continue
        try:
            data = client.fetch_bank_list(url)
        except Exception:
            continue
        rows = data if isinstance(data, list) else (data.get('data') or data.get('bankDetails') or [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            iin = str(row.get('iin') or row.get('IIN') or row.get('nationalBankIdentificationNumber') or '').strip()
            name = str(row.get('bankName') or row.get('name') or '').strip()
            if not iin or not name:
                continue
            AepsBankIinCache.objects.update_or_create(
                list_type=list_type,
                iin=iin,
                defaults={'bank_name': name, 'raw': scrub_sensitive(row), 'is_active': True},
            )
            count += 1
    return count


def list_banks(list_type: str = 'aeps'):
    return list(
        AepsBankIinCache.objects.filter(list_type=list_type, is_active=True).values('iin', 'bank_name')
    )


def serialize_txn(txn: AepsTransaction) -> dict:
    meta = txn.provider_meta if isinstance(txn.provider_meta, dict) else {}
    return {
        'id': txn.pk,
        'merchant_tran_id': txn.merchant_tran_id,
        'product': txn.product,
        'status': txn.status,
        'amount': str(txn.amount),
        'fee_amount': str(txn.fee_amount),
        'commission_amount': str(txn.commission_amount),
        'bank_iin': txn.bank_iin,
        'bank_name': txn.bank_name,
        'masked_aadhaar': txn.masked_aadhaar,
        'customer_mobile': txn.customer_mobile,
        'fp_transaction_id': txn.fp_transaction_id,
        'bank_rrn': txn.bank_rrn,
        'response_code': txn.response_code,
        'response_message': txn.response_message,
        'balance_amount': str(txn.balance_amount) if txn.balance_amount is not None else None,
        'mini_statement': txn.mini_statement or [],
        'acknowledged': txn.acknowledged,
        'cd_otp_mode': bool(meta.get('cd_otp_mode')),
        'cd_otp_step': meta.get('cd_otp_step') or '',
        'created_at': txn.created_at.isoformat() if txn.created_at else None,
    }
