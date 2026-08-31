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


CAPTURE_RESPONSE_KEYS = (
    'PidDatatype',
    'Piddata',
    'ci',
    'dc',
    'dpID',
    'errCode',
    'errInfo',
    'fCount',
    'fType',
    'hmac',
    'iCount',
    'iType',
    'mc',
    'mi',
    'nmPoints',
    'pCount',
    'pType',
    'qScore',
    'rdsID',
    'rdsVer',
    'sessionKey',
)


def normalize_capture_response(capture_response) -> dict:
    """
    Keep only the 21 Fingpay CaptureResponse fields, in the sample JSON order.
    Piddata must be the RD <Data> payload — never raw XML (that is the old
    frontend fallback that UIDAI reports as missing biometric data).
    """
    if not isinstance(capture_response, dict):
        raise ValidationError(
            {
                'code': 'DEVICE_REQUIRED',
                'message': (
                    'Fingerprint capture data is missing (no PID block from the RD service). '
                    'Capture the finger again before submitting.'
                ),
            }
        )
    pid = str(capture_response.get('Piddata') or capture_response.get('PidData') or '').strip()
    if not pid or pid.lstrip().startswith('<'):
        raise ValidationError(
            {
                'code': 'DEVICE_REQUIRED',
                'message': (
                    'Fingerprint capture data is missing (no PID block from the RD service). '
                    'Capture the finger again before submitting.'
                ),
            }
        )
    src = capture_response
    return {
        'PidDatatype': str(src.get('PidDatatype') or src.get('PidDataType') or 'X'),
        'Piddata': pid,
        'ci': str(src.get('ci') or ''),
        'dc': str(src.get('dc') or ''),
        'dpID': str(src.get('dpID') or src.get('dpId') or ''),
        'errCode': str(src.get('errCode') or '0'),
        'errInfo': str(src.get('errInfo') or 'Success'),
        'fCount': str(src.get('fCount') or '1'),
        'fType': str(src.get('fType') or '2'),
        'hmac': str(src.get('hmac') or ''),
        'iCount': str(src.get('iCount') or '0'),
        'iType': str(src.get('iType') or '0'),
        'mc': str(src.get('mc') or ''),
        'mi': str(src.get('mi') or ''),
        'nmPoints': str(src.get('nmPoints') or ''),
        'pCount': str(src.get('pCount') or '0'),
        'pType': str(src.get('pType') or '0'),
        'qScore': str(src.get('qScore') or ''),
        'rdsID': str(src.get('rdsID') or src.get('rdsId') or ''),
        'rdsVer': str(src.get('rdsVer') or ''),
        'sessionKey': str(src.get('sessionKey') or ''),
    }


def assert_capture_has_biometric(capture_response) -> None:
    """UIDAI 3552: empty / XML-as-Piddata capture must not be posted."""
    normalize_capture_response(capture_response)


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
    capture_response = normalize_capture_response(capture_response)
    client = get_fingpay_client()
    today = timezone.localdate()
    row, _ = AepsDaily2FA.objects.get_or_create(merchant=merchant, for_date=today, defaults={'status': 'pending'})
    payload = payload or {}
    # Docs: transactionType=AUO, serviceType=AEPS|AP (internal product remains 2FA)
    service_type = str(payload.get('serviceType') or 'AEPS').upper()
    if service_type not in ('AEPS', 'AP'):
        service_type = 'AEPS'
    merchant_tran_id = generate_merchant_tran_id('2FA')
    # 2FA BIOMETRIC API DOCUMENT sample key order. Do not send timestamp in the
    # body — that field is Mini Statement / product only; it is not in the 2.1 sample.
    body = twofa_request_body(
        merchant=merchant,
        client=client,
        capture_response=capture_response,
        latitude=latitude,
        longitude=longitude,
        payload=payload,
        merchant_tran_id=merchant_tran_id,
        service_type=service_type,
    )
    txn = AepsTransaction.objects.create(
        user=user,
        merchant=merchant,
        merchant_tran_id=merchant_tran_id,
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
        resp = client.aeps_post(
            path_2fa,
            body,
            device_imei=merchant.device_imei,
            endpoint_key='twofa_validate',
            include_body_timestamp=False,
        )
    except Exception as exc:
        txn.status = 'failed'
        txn.response_message = str(exc)[:500]
        txn.save()
        row.status = 'failed'
        row.message = str(exc)[:500]
        row.save()
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc

    data = resp.get('data') if isinstance(resp.get('data'), dict) else {}
    # 2FA PDF checklist: success only when data.responseCode is '00'.
    ok = twofa_is_success(data)
    txn.status = 'success' if ok else 'failed'
    txn.response_code = str((data or {}).get('responseCode') or resp.get('statusCode') or '')
    txn.response_message = explain_provider_failure(resp, data, merchant)[:500]
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


def twofa_is_success(data) -> bool:
    """2FA PDF: consider auth success only when the inner responseCode is '00'."""
    return str((data or {}).get('responseCode') or '') == '00'


def twofa_request_body(
    *,
    merchant,
    client,
    capture_response: dict,
    latitude,
    longitude,
    payload: dict,
    merchant_tran_id: str,
    service_type: str = 'AEPS',
) -> dict:
    """Plain JSON for Simple 2FA — key order matches the 2.1 sample request."""
    return {
        'captureResponse': capture_response,
        'cardnumberORUID': _card_from_payload(payload),
        'latitude': float(latitude),
        'longitude': float(longitude),
        'requestRemarks': payload.get('requestRemarks') or '2fa',
        'transactionType': 'AUO',
        'merchantUserName': _merchant_user_name(merchant),
        'merchantPin': _txn_merchant_pin(merchant, client),
        'superMerchantId': _super_merchant_id(client),
        'merchantTranId': merchant_tran_id,
        'mobileNumber': str(payload.get('mobileNumber') or ''),
        'serviceType': service_type,
    }


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
    capture_response = normalize_capture_response(capture_response)
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
                'Fingpay HTTP 403 (AWS ELB blocked the host before the application). '
                f'Confirm with Tapits that our egress IP is whitelisted. {_provider_support_context(merchant)}. '
                f'Detail: {err}'
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


def _provider_support_context(merchant=None) -> str:
    """Login / superMerchantId / egress for Tapits tickets (best-effort)."""
    parts: list[str] = []
    login = str(getattr(merchant, 'merchant_login_id', '') or '').strip()
    if login:
        parts.append(f'merchantLoginId={login}')
    try:
        client = get_fingpay_client()
        smid = str(getattr(client, 'super_merchant_id', '') or '').strip()
        if smid:
            parts.append(f'superMerchantId={smid}')
        egress = str(getattr(client, 'effective_egress_ip', '') or '').strip()
        if egress:
            parts.append(f'egressIP={egress}')
        env = str(getattr(client, 'environment', '') or getattr(client, 'api_mode', '') or '').strip()
        if env:
            parts.append(f'env={env}')
    except Exception:
        pass
    return '; '.join(parts)


def _identity_reject_message(resp: dict, merchant=None) -> str:
    """Map Fingpay identity / product-disabled codes to actionable UI text."""
    code = str(resp.get('statusCode') or '')
    msg = str(resp.get('message') or '')
    msg_l = msg.lower()
    login = str(getattr(merchant, 'merchant_login_id', '') or '').strip()
    who = login or 'this merchant'
    ctx = _provider_support_context(merchant)

    # 10027 is reused: daily product limits AND merchant AEPS-disabled. Match the text.
    if 'daily limit' in msg_l or 'exceeded daily limit' in msg_l:
        product_hint = ''
        if 'balance inquir' in msg_l:
            product_hint = (
                ' Balance enquiry has a per-day cap at Fingpay. '
                'Mini statement and other AEPS products may still work.'
            )
        return (
            f'{msg} ({code or "10027"}).{product_hint} '
            'This is not an IP, hash, fingerprint, or URL issue.'
        )[:500]

    if 'aeps services is temporarily disabled' in msg_l or (
        code == '10027' and 'disabled' in msg_l and 'limit' not in msg_l
    ):
        return (
            f'Fingpay disabled AEPS for {who} (10027). '
            'This is not an IP, hash, fingerprint, or URL issue — Tapits must enable AEPS on '
            'fpaepsservice for this super-merchant/merchant. '
            f'Support context: {ctx or "see Admin → AEPS Provider"}.'
        )[:500]

    if code == '10006' or 'incorrect merchantid or pin' in msg_l:
        return (
            f'Fingpay rejected {who} (10006 Incorrect merchantId or pin). '
            'Admin: Reset PIN / Re-sync onboarding (Simple create on fingpayap), then retry on '
            'fingpayap.tapits.in/fpaepsservice (not fpuat). '
            f'{ctx}'
        )[:500]

    if code == '10005' and (
        'merchant' in msg_l or 'invalid merchant' in msg_l or 'does not recognise' in msg_l
    ):
        return (
            f'Fingpay does not recognise {who} on the AEPS 2FA/txn API (10005). '
            'eKYC may be complete, but Tapits must activate this User Id on fpaepsservice. '
            f'{ctx}'
        )[:500]

    return ''


def _parse_balance_amount(data: dict):
    """Pick a real account balance; skip Fingpay's -1.00 failure sentinel."""
    if not isinstance(data, dict):
        return None
    for key in ('balanceAmount', 'bankAccountBalance', 'miniStatementBalance'):
        raw = data.get(key)
        if raw is None or raw == '':
            continue
        try:
            val = Decimal(str(raw).strip().replace(',', ''))
        except Exception:
            continue
        if val < 0:
            continue
        return val
    return None


def _parse_mini_statement(data: dict):
    """Prefer on-us lines; fall back to off-us / legacy keys. Empty list is valid."""
    if not isinstance(data, dict):
        return None
    on_us = data.get('miniStatementStructureModel')
    off_us = data.get('miniOffusStatementStructureModel')
    legacy = data.get('miniStatement')
    if not isinstance(legacy, list):
        legacy = data.get('statement')
    for candidate in (on_us, off_us, legacy):
        if isinstance(candidate, list) and candidate:
            return candidate
    for candidate in (on_us, off_us, legacy):
        if isinstance(candidate, list):
            return candidate
    return None


def _biometric_reject_message(inner_code: str, inner_msg: str) -> str:
    """
    Explain UIDAI-level rejections that arrive inside `data`, where the outer
    envelope only says "Transaction failed." and hides the real cause.
    """
    m = (inner_msg or '').lower()

    if 'missing biometric data' in m:
        return (
            f'UIDAI rejected the fingerprint ({inner_code}): {inner_msg}. '
            'The capture reached UIDAI but carried no usable finger record. '
            'Recapture with the RD service; if it keeps failing, the reader is not producing '
            'the finger format this request asks for — change the AEPS capture fType in '
            'Admin → AEPS Provider and retry.'
        )[:500]

    if 'biometric' in m and ('did not match' in m or 'not match' in m):
        return (
            f'UIDAI could not match the fingerprint ({inner_code}): {inner_msg}. '
            'Clean the sensor and retry with a different finger.'
        )[:500]

    if 'biometric' in m and 'lock' in m:
        return (
            f'UIDAI reports biometrics locked for this Aadhaar ({inner_code}): {inner_msg}. '
            'The holder must unlock biometrics on the UIDAI portal before AEPS will work.'
        )[:500]

    return ''


def explain_provider_failure(resp: dict, data: dict, merchant=None) -> str:
    """
    Best available failure text: identity/entitlement mapping first, then the
    UIDAI detail from `data`, then the provider's inner message, and only then
    the outer envelope message (which is usually just "Transaction failed.").
    """
    identity = _identity_reject_message(resp, merchant)
    if identity:
        return identity

    data = data if isinstance(data, dict) else {}
    inner_code = str(data.get('responseCode') or '')
    inner_msg = str(data.get('responseMessage') or data.get('errorMessage') or '')

    biometric = _biometric_reject_message(inner_code, inner_msg)
    if biometric:
        return biometric

    if inner_msg:
        return (f'{inner_msg} ({inner_code})' if inner_code else inner_msg)[:500]
    return str(resp.get('message') or '')[:500]


def apply_provider_result(txn: AepsTransaction, resp: dict, data: dict) -> None:
    txn.response_code = str(data.get('responseCode') or resp.get('statusCode') or '')
    txn.response_message = explain_provider_failure(resp, data, getattr(txn, 'merchant', None))[:500]
    txn.fp_transaction_id = str(
        data.get('fpTransactionId') or data.get('fingpayTransactionId') or data.get('fpTxnId') or ''
    )
    txn.bank_rrn = str(data.get('bankRRN') or data.get('bankRrn') or data.get('rrn') or '')
    if data.get('bankName'):
        txn.bank_name = str(data.get('bankName'))[:120]
    bal = _parse_balance_amount(data)
    if bal is not None:
        txn.balance_amount = bal
    rows = _parse_mini_statement(data)
    if rows is not None:
        txn.mini_statement = rows
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
