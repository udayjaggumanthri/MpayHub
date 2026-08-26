"""AEPS product flows: 2FA, BE, MS, CW, AP, CD + status mid-points / ack."""
from __future__ import annotations

from decimal import Decimal

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.aeps.models import AepsBankIinCache, AepsDaily2FA, AepsTransaction
from apps.aeps.services.gates import (
    assert_daily_2fa,
    assert_device_ready,
    assert_merchant_active,
)
from apps.aeps.services.ids import generate_merchant_tran_id, merchant_pin_plain
from apps.integrations.fingpay.crypto import mask_aadhaar, md5_hex, scrub_sensitive, trn_timestamp_now
from apps.integrations.fingpay.endpoints import ACK_PATH_KEYS, PRODUCT_PATH_KEYS, STATUS_PATH_KEYS, default_endpoints_for
from apps.integrations.fingpay.registry import get_active_provider, get_fingpay_client

# Defaults kept for tests / fallbacks (admin endpoints_json overrides via client)
_DEFAULTS = default_endpoints_for(environment='prod', onboarding_api_style='php')
PATH_CW = _DEFAULTS['cw']
PATH_BE = _DEFAULTS['be']
PATH_MS = _DEFAULTS['ms']
PATH_AP = _DEFAULTS['ap']
PATH_CD = _DEFAULTS['cd']
PATH_CD_OTP_GENERATE = _DEFAULTS['cd_otp_generate']
PATH_CD_OTP_VALIDATE = _DEFAULTS['cd_otp_validate']
PATH_CD_OTP_TXN = _DEFAULTS['cd_otp_txn']
PATH_2FA = _DEFAULTS['twofa_validate']
ACK_CW = _DEFAULTS['ack_cw']
ACK_CD = _DEFAULTS['ack_cd']
ACK_CD_OTP = _DEFAULTS['ack_cd_otp']

STATUS_PATHS = {
    'CW': _DEFAULTS['status_cw'],
    'CD': _DEFAULTS['status_cd'],
    'CD_OTP': _DEFAULTS['status_cd_otp'],
    'AP': _DEFAULTS['status_ap'],
    'BE': _DEFAULTS['status_cw'],
    'MS': _DEFAULTS['status_cw'],
}

ACK_PATHS = {
    'CW': ACK_CW,
    'AP': ACK_CW,
    'CD': ACK_CD,
    'CD_OTP': ACK_CD_OTP,
}


def _path_from_client(client, key: str, fallback: str) -> str:
    return client.endpoint(key, fallback) if client else fallback


def status_path_for_product(product: str, *, otp_mode: bool = False, client=None) -> str:
    if otp_mode or product == 'CD_OTP':
        key = STATUS_PATH_KEYS['CD_OTP']
        return _path_from_client(client, key, STATUS_PATHS['CD_OTP'])
    key = STATUS_PATH_KEYS.get(product, 'status_cw')
    return _path_from_client(client, key, STATUS_PATHS.get(product, STATUS_PATHS['CW']))


def ack_path_for_product(product: str, *, otp_mode: bool = False, client=None) -> str:
    if otp_mode or product == 'CD_OTP':
        return _path_from_client(client, 'ack_cd_otp', ACK_CD_OTP)
    key = ACK_PATH_KEYS.get(product, 'ack_cw')
    return _path_from_client(client, key, ACK_PATHS.get(product, ACK_CW))


def product_path(product: str, *, client=None) -> str:
    key = PRODUCT_PATH_KEYS.get(product, product.lower())
    fallback = {
        'CW': PATH_CW,
        'BE': PATH_BE,
        'MS': PATH_MS,
        'AP': PATH_AP,
        'CD': PATH_CD,
    }.get(product, '')
    return _path_from_client(client, key, fallback)


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


def _is_simple_api(client) -> bool:
    return getattr(client, 'api_mode', '') == 'simple' or getattr(client, 'onboarding_api_style', '') == 'simple'


def _super_merchant_id(client):
    raw = client.super_merchant_id
    return int(raw) if str(raw).isdigit() else raw


def _txn_merchant_pin(merchant, client) -> str:
    """
    Onboarding Simple API: merchantLoginPin = plain pin (e.g. 2590).
    Mini Statement spec: merchantPin = MD5(plain) uppercase
    (sample 81DC9BDB… = MD5('1234')). Encrypted txn APIs use MD5 lowercase.
    """
    pin = merchant_pin_plain(merchant)
    if not pin:
        return ''
    digest = pin.lower() if len(pin) == 32 and all(c in '0123456789abcdefABCDEF' for c in pin) else md5_hex(pin)
    if _is_simple_api(client):
        return digest.upper()
    return digest


def _card_from_payload(payload: dict) -> dict:
    card = payload.get('cardnumberORUID') if isinstance(payload.get('cardnumberORUID'), dict) else {}
    raw = str(
        card.get('adhaarNumber') or payload.get('aadhaarNumber') or payload.get('adhaarNumber') or ''
    )
    digits = ''.join(c for c in raw if c.isdigit())
    if 'x' in raw.lower() or len(digits) != 12:
        raise ValidationError(
            {
                'code': 'AADHAAR_REQUIRED',
                'message': 'Enter the full 12-digit customer Aadhaar. Masked values are not sent to Fingpay.',
            }
        )
    out = {
        'adhaarNumber': digits,
        'indicatorforUID': int(card.get('indicatorforUID') or payload.get('indicatorforUID') or 0),
        'nationalBankIdentificationNumber': str(
            card.get('nationalBankIdentificationNumber')
            or payload.get('nationalBankIdentificationNumber')
            or payload.get('iin')
            or ''
        ),
    }
    virtual_id = card.get('virtualId') or payload.get('virtualId')
    if virtual_id:
        out['virtualId'] = str(virtual_id)
    return out


def _merchant_mobile(merchant) -> str:
    """10-digit merchant mobile used as Fingpay merchantUserName."""
    payload = getattr(merchant, 'onboarding_payload', None)
    payload = payload if isinstance(payload, dict) else {}
    nested = payload.get('merchant') if isinstance(payload.get('merchant'), dict) else {}
    raw = (
        payload.get('merchantPhoneNumber')
        or nested.get('merchantPhoneNumber')
        or getattr(getattr(merchant, 'user', None), 'phone', None)
        or ''
    )
    digits = ''.join(c for c in str(raw) if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def _merchant_user_name(merchant) -> str:
    """
    Fingpay txn APIs: merchantUserName = login id created at onboarding
    (e.g. MPH20182), not the mobile number. Mobile stays in mobileNumber.
    """
    login_id = str(getattr(merchant, 'merchant_login_id', '') or '').strip()
    if login_id:
        return login_id
    return _merchant_mobile(merchant)


def _base_merchant_fields(merchant, client) -> dict:
    # Mini Statement doc: subMerchantId is only for the "single merchant id and pin"
    # aggregator case. MPH20182 has its own login+pin, and Fingpay has not told
    # us this account requires subMerchantId — do not send it.
    return {
        'merchantUserName': _merchant_user_name(merchant),
        'merchantPin': _txn_merchant_pin(merchant, client),
        'superMerchantId': _super_merchant_id(client),
        'languageCode': 'en',
        'paymentType': 'B',
        'timestamp': trn_timestamp_now(),
    }


def _simple_txn_body(
    *,
    merchant,
    client,
    product: str,
    payload: dict,
    capture_response: dict,
    latitude,
    longitude,
    amount,
    merchant_tran_id: str,
) -> dict:
    """
    SIMPLE API FOR MINISTATEMENT sample JSON key order.
    Hash is Base64(SHA256(compactJson + secretKey + trnTimestamp)), so order
    is part of the hashed string; keep it identical to the published sample.
    """
    base = _base_merchant_fields(merchant, client)
    txn_type = {'CW': 'CW', 'BE': 'BE', 'MS': 'MS', 'AP': 'M', 'CD': 'CD'}.get(product, product)
    body = {
        'merchantTranId': merchant_tran_id,
        'captureResponse': capture_response,
        'cardnumberORUID': _card_from_payload(payload),
        'languageCode': base.get('languageCode') or 'en',
        'latitude': float(latitude),
        'longitude': float(longitude),
        'mobileNumber': payload.get('mobileNumber') or '',
        'paymentType': base.get('paymentType') or 'B',
        'requestRemarks': payload.get('requestRemarks') or product,
        'timestamp': base.get('timestamp') or trn_timestamp_now(),
        'transactionAmount': float(amount or 0),
        'transactionType': txn_type,
        'merchantUserName': base['merchantUserName'],
        'merchantPin': base['merchantPin'],
        'superMerchantId': base['superMerchantId'],
        'deviceTransactionId': merchant_tran_id,
    }
    # Encrypted PHP Balance Enquiry used merchantTransactionId — keep both for BE.
    if product == 'BE':
        body['merchantTransactionId'] = merchant_tran_id
    return body


def complete_daily_2fa(*, user, capture_response: dict, latitude, longitude, payload: dict | None = None) -> dict:
    merchant = assert_merchant_active(user)
    assert_device_ready(merchant)
    client = get_fingpay_client()
    today = timezone.localdate()
    row, _ = AepsDaily2FA.objects.get_or_create(merchant=merchant, for_date=today, defaults={'status': 'pending'})
    payload = payload or {}
    # Docs: transactionType=AUO, serviceType=AEPS|AP (internal product remains 2FA)
    service_type = str(payload.get('serviceType') or 'AEPS').upper()
    if service_type not in ('AEPS', 'AP'):
        service_type = 'AEPS'
    # 2FA BIOMETRIC API DOCUMENT — same identity as Mini Statement (no subMerchantId
    # unless Fingpay says this account uses a single company merchant id/pin).
    body = {
        'superMerchantId': _super_merchant_id(client),
        'merchantUserName': _merchant_user_name(merchant),
        'merchantPin': _txn_merchant_pin(merchant, client),
        'transactionType': 'AUO',
        'latitude': float(latitude),
        'longitude': float(longitude),
        'requestRemarks': payload.get('requestRemarks') or '2fa',
        'merchantTranId': generate_merchant_tran_id('2FA'),
        'serviceType': service_type,
        'mobileNumber': str(payload.get('mobileNumber') or ''),
        'cardnumberORUID': _card_from_payload(payload),
        'captureResponse': capture_response,
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
    path_2fa = _path_from_client(client, 'twofa_validate', PATH_2FA)
    try:
        resp = client.aeps_post(path_2fa, body, device_imei=merchant.device_imei, endpoint_key='twofa_validate')
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
    txn.response_message = (
        _identity_reject_message(resp, merchant) or str(resp.get('message') or '')
    )[:500]
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
    path: str | None = None,
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
    path = path or product_path(product, client=client)
    endpoint_key = PRODUCT_PATH_KEYS.get(product, product.lower())

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

    if _is_simple_api(client):
        body = _simple_txn_body(
            merchant=merchant,
            client=client,
            product=product,
            payload=payload,
            capture_response=capture_response,
            latitude=latitude,
            longitude=longitude,
            amount=amount,
            merchant_tran_id=txn.merchant_tran_id,
        )
    else:
        card = _card_from_payload(payload)
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
            'merchantTranId': txn.merchant_tran_id,
        }
        if product == 'BE':
            body['merchantTransactionId'] = txn.merchant_tran_id

    txn.status = 'pending'
    txn.save(update_fields=['status', 'updated_at'])

    try:
        resp = client.aeps_post(path, body, device_imei=merchant.device_imei, endpoint_key=endpoint_key)
    except Exception as exc:
        from apps.integrations.fingpay.client import FingpayClientError

        err = str(exc)[:500]
        status_code = getattr(exc, 'status_code', None) if isinstance(exc, FingpayClientError) else None
        if status_code == 403 or 'HTTP 403' in err:
            txn.status = 'failed'
            txn.response_code = '403'
            txn.response_message = (
                'Fingpay HTTP 403 (AWS ELB blocked the host). Tapits asked us to use '
                'production Mini Statement fingpayap.tapits.in and said 139.99.47.143 '
                f'is already whitelisted. Share this 403 with Tapits. Detail: {err}'
            )[:500]
            txn.save()
            return {'transaction': serialize_txn(txn), 'needs_status_check': False, 'error': txn.response_message}
        txn.status = 'timeout'
        txn.response_message = err
        txn.save()
        return {'transaction': serialize_txn(txn), 'needs_status_check': True, 'error': err}

    data = resp.get('data') if isinstance(resp.get('data'), dict) else {}
    apply_provider_result(txn, resp, data)
    if txn.status == 'success':
        try:
            acknowledge_transaction(txn)
        except Exception as ack_exc:
            import logging

            logging.getLogger(__name__).warning('AEPS ack failed for %s: %s', txn.merchant_tran_id, ack_exc)
    return {'transaction': serialize_txn(txn), 'needs_status_check': txn.status == 'pending'}


def _identity_reject_message(resp: dict, merchant=None) -> str:
    """10006/10005 after successful eKYC means Fingpay txn DB has not activated the merchant."""
    code = str(resp.get('statusCode') or '')
    msg = str(resp.get('message') or '')
    login = str(getattr(merchant, 'merchant_login_id', '') or '').strip()
    if code == '10006' or 'incorrect merchantid or pin' in msg.lower():
        who = login or 'this merchant'
        return (
            f'Fingpay Mini Statement rejected {who} (10006 Incorrect merchantId or pin). '
            'Reset the merchant PIN by re-hitting Simple onboarding on fingpayap, then retry Mini Statement '
            'on fingpayap.tapits.in/fpaepsservice (not fpuat).'
        )[:500]
    if code == '10005' and 'merchant' in msg.lower():
        who = login or 'this merchant'
        return (
            f'Fingpay does not recognise {who} on the AEPS 2FA/txn API (10005). '
            'eKYC is complete; ask Tapits to activate this User Id on fpaepsservice.'
        )[:500]
    return ''


def apply_provider_result(txn: AepsTransaction, resp: dict, data: dict) -> None:
    txn.response_code = str(data.get('responseCode') or resp.get('statusCode') or '')
    explained = _identity_reject_message(resp, getattr(txn, 'merchant', None))
    txn.response_message = (
        explained
        or str(data.get('responseMessage') or data.get('errorMessage') or resp.get('message') or '')
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
    if isinstance(data.get('miniStatementStructureModel'), list):
        txn.mini_statement = data.get('miniStatementStructureModel')
    elif isinstance(data.get('miniStatement'), list):
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
    import logging

    if txn.acknowledged or txn.status != 'success':
        return
    client = get_fingpay_client()
    path = ack_path_for_product(txn.product, otp_mode=otp_mode, client=client)
    ack_key = 'ack_cd_otp' if (otp_mode or txn.product == 'CD_OTP') else ACK_PATH_KEYS.get(txn.product, 'ack_cw')
    body = {
        'merchantTransactionId': txn.merchant_tran_id,
        'fingpayTransactionId': txn.fp_transaction_id,
        'acknowledgementStatus': True,
        'rrn': txn.bank_rrn,
        'responseCode': txn.response_code or '00',
    }
    try:
        client.aeps_post(path, body, device_imei=txn.device_imei or 'UNKNOWN', endpoint_key=ack_key)
        txn.acknowledged = True
        txn.acknowledged_at = timezone.now()
        txn.save(update_fields=['acknowledged', 'acknowledged_at', 'updated_at'])
    except Exception as exc:
        logging.getLogger(__name__).warning(
            'AEPS acknowledge failed merchant_tran_id=%s: %s', txn.merchant_tran_id, exc
        )
        raise


def status_check(*, user, merchant_tran_id: str, otp_mode: bool = False) -> dict:
    merchant = assert_merchant_active(user)
    try:
        txn = AepsTransaction.objects.get(user=user, merchant_tran_id=merchant_tran_id, is_deleted=False)
    except AepsTransaction.DoesNotExist as exc:
        raise ValidationError({'message': 'Transaction not found'}) from exc
    client = get_fingpay_client()
    path = status_path_for_product(txn.product, otp_mode=otp_mode, client=client)
    status_key = STATUS_PATH_KEYS.get(
        'CD_OTP' if (otp_mode or txn.product == 'CD_OTP') else txn.product,
        'status_cw',
    )
    body = {
        **_base_merchant_fields(merchant, client),
        'merchantTranId': txn.merchant_tran_id,
        'merchantTransactionId': txn.merchant_tran_id,
        'transactionType': txn.product,
        'fingpayTransactionId': txn.fp_transaction_id or '',
    }
    try:
        resp = client.status_check(
            path,
            body,
            merchant_tran_id=txn.merchant_tran_id,
            merchant_login_id=merchant.merchant_login_id,
            device_imei=merchant.device_imei,
            endpoint_key=status_key,
        )
    except Exception as exc:
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc
    data = resp.get('data') if isinstance(resp.get('data'), dict) else {}
    apply_provider_result(txn, resp, data)
    if txn.status == 'success':
        try:
            acknowledge_transaction(txn, otp_mode=otp_mode or txn.product == 'CD_OTP')
        except Exception:
            pass
    return {'transaction': serialize_txn(txn), 'status_path': path}


def cash_withdrawal(**kwargs):
    return _run_product(product='CW', require_2fa=True, **kwargs)


def balance_enquiry(**kwargs):
    return _run_product(product='BE', require_2fa=False, **kwargs)


def mini_statement(**kwargs):
    return _run_product(product='MS', require_2fa=False, **kwargs)


def aadhaar_pay(**kwargs):
    return _run_product(product='AP', require_2fa=True, **kwargs)


def cash_deposit(**kwargs):
    return _run_product(product='CD', require_2fa=True, **kwargs)


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
        resp = client.aeps_post(
            _path_from_client(client, 'cd_otp_generate', PATH_CD_OTP_GENERATE),
            body,
            device_imei=merchant.device_imei,
            endpoint_key='cd_otp_generate',
        )
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
        resp = client.aeps_post(
            _path_from_client(client, 'cd_otp_validate', PATH_CD_OTP_VALIDATE),
            body,
            device_imei=merchant.device_imei,
            endpoint_key='cd_otp_validate',
        )
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
        resp = client.aeps_post(
            _path_from_client(client, 'cd_otp_txn', PATH_CD_OTP_TXN),
            body,
            device_imei=merchant.device_imei,
            endpoint_key='cd_otp_txn',
        )
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
    errors = []
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
        except Exception as exc:
            errors.append(f'{list_type}: {exc}')
            continue
        rows = data if isinstance(data, list) else (data.get('data') or data.get('bankDetails') or [])
        if not isinstance(rows, list):
            errors.append(f'{list_type}: unexpected response shape')
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            # Fingpay bank list uses iinno (docs + live UAT/prod response).
            iin = str(
                row.get('iinno')
                or row.get('iin')
                or row.get('IIN')
                or row.get('nationalBankIdentificationNumber')
                or ''
            ).strip()
            name = str(row.get('bankName') or row.get('name') or row.get('details') or '').strip()
            if not iin or iin.upper() in ('NULL', 'NONE', 'N/A') or not name:
                continue
            if not iin.isdigit():
                continue
            AepsBankIinCache.objects.update_or_create(
                list_type=list_type,
                iin=iin,
                defaults={'bank_name': name, 'raw': scrub_sensitive(row), 'is_active': True},
            )
            count += 1
    if count == 0 and errors:
        raise ValidationError({'message': 'Bank list sync failed: ' + '; '.join(errors)})
    return count


def list_banks(list_type: str = 'aeps', *, auto_sync: bool = True):
    list_type = 'aadhaar_pay' if list_type in ('aadhaar_pay', 'ap', 'aadhaarpay') else 'aeps'
    rows = list(
        AepsBankIinCache.objects.filter(list_type=list_type, is_active=True)
        .order_by('bank_name')
        .values('iin', 'bank_name')
    )
    if auto_sync and not rows:
        try:
            sync_bank_iin_cache()
        except Exception:
            return []
        rows = list(
            AepsBankIinCache.objects.filter(list_type=list_type, is_active=True)
            .order_by('bank_name')
            .values('iin', 'bank_name')
        )
    return rows


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
