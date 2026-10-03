"""
BillAvenue remitter / paymentInfo compliance (feature-flagged).

Used only when BillAvenueConfig.remitter_compliance_enabled is True.
Does not touch wallet, settlement, commission, or float.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.core.exceptions import TransactionFailed

HIGH_VALUE_RUPEES = Decimal('50000')

MSG_REMITTER_INCOMPLETE = (
    'Payment details are incomplete. Enter PAN or Aadhaar and try again.'
)
MSG_REMITTER_NAME = (
    'Remitter details are missing. Update profile name and fetch bill again before payment.'
)
MSG_VPA_INVALID = (
    'Enter a valid UPI ID (VPA) that includes @, then try payment again.'
)
MSG_CARD_DETAILS = (
    'Card payment details are incomplete. Enter last 4 digits, card issuer, and auth code.'
)
MSG_ACCOUNT_INFO = (
    'Payment account details are incomplete for this payment method. Please try again.'
)


def is_remitter_compliance_enabled(config) -> bool:
    if config is None:
        return False
    return bool(getattr(config, 'remitter_compliance_enabled', False))


def _norm_mode(payment_mode: str) -> str:
    return str(payment_mode or '').strip().lower().replace('_', ' ').replace('-', ' ')


def _norm_info_name(name: str) -> str:
    return ' '.join(str(name or '').strip().lower().split())


def _scalar(d: dict | None, *keys: str) -> str:
    if not isinstance(d, dict):
        return ''
    lowered = {str(k).strip().lower(): v for k, v in d.items()}
    for key in keys:
        raw = d.get(key)
        if raw is None:
            raw = lowered.get(str(key).strip().lower())
        if raw is not None and not isinstance(raw, (dict, list)):
            s = str(raw).strip()
            if s:
                return s
    return ''


def _amount_rupees(amount) -> Decimal:
    try:
        return Decimal(str(amount or '0'))
    except Exception:
        return Decimal('0')


def is_high_value_amount(amount) -> bool:
    """BillAvenue high-value remitter set applies when amount is greater than 50000."""
    return _amount_rupees(amount) > HIGH_VALUE_RUPEES


def extract_identity(*, bill_data: dict) -> tuple[str, str]:
    """
    Return (kind, value) where kind is 'PAN' or 'Aadhaar', or ('', '').
    Prefer client-supplied values; never invent IDs.
    """
    if not isinstance(bill_data, dict):
        return '', ''
    ci = bill_data.get('customer_info') if isinstance(bill_data.get('customer_info'), dict) else {}
    cd = bill_data.get('customer_details') if isinstance(bill_data.get('customer_details'), dict) else {}

    pan = _scalar(ci, 'customerPan', 'customer_pan', 'PAN', 'pan')
    if not pan:
        pan = _scalar(cd, 'PAN', 'pan', 'Customer PAN')
    if pan:
        return 'PAN', pan.upper()

    aadhaar = _scalar(ci, 'customerAadhaar', 'customer_aadhaar', 'Aadhaar', 'aadhaar')
    if not aadhaar:
        aadhaar = _scalar(cd, 'Aadhaar', 'aadhaar', 'Customer Aadhaar')
    if aadhaar:
        digits = ''.join(ch for ch in aadhaar if ch.isdigit())
        return 'Aadhaar', digits or aadhaar
    return '', ''


def _resolve_vpa(*, bill_data: dict) -> str:
    cd = bill_data.get('customer_details') if isinstance(bill_data.get('customer_details'), dict) else {}
    ci = bill_data.get('customer_info') if isinstance(bill_data.get('customer_info'), dict) else {}
    return (
        _scalar(bill_data, 'vpa', 'VPA')
        or _scalar(cd, 'VPA', 'vpa', 'UPI ID')
        or _scalar(ci, 'vpa', 'VPA')
    )


def _card_last4_issuer(*, bill_data: dict) -> tuple[str, str]:
    cd = bill_data.get('customer_details') if isinstance(bill_data.get('customer_details'), dict) else {}
    ci = bill_data.get('customer_info') if isinstance(bill_data.get('customer_info'), dict) else {}
    last4 = (
        _scalar(cd, 'Card Last4 Digits', 'Card Last 4 Digits', 'CardNum', 'card_last4')
        or _scalar(ci, 'cardLast4', 'card_last4', 'CardNum')
        or _scalar(bill_data, 'card_last4', 'CardNum')
    )
    issuer = (
        _scalar(cd, 'Card Issuer', 'card_issuer', 'Issuer')
        or _scalar(ci, 'cardIssuer', 'card_issuer')
        or _scalar(bill_data, 'card_issuer')
    )
    return last4, issuer


def _auth_code(*, bill_data: dict) -> str:
    cd = bill_data.get('customer_details') if isinstance(bill_data.get('customer_details'), dict) else {}
    ci = bill_data.get('customer_info') if isinstance(bill_data.get('customer_info'), dict) else {}
    return (
        _scalar(cd, 'AuthCode', 'Auth Code', 'auth_code')
        or _scalar(ci, 'authCode', 'auth_code', 'AuthCode')
        or _scalar(bill_data, 'auth_code', 'AuthCode')
    )


def derive_payment_account_info(
    *,
    payment_mode: str,
    bill_data: dict,
    correlation_ref: str = '',
) -> str:
    """BillAvenue Payment Account Info table."""
    mode = _norm_mode(payment_mode)
    payment_ref = str(correlation_ref or '').strip()
    ci = bill_data.get('customer_info') if isinstance(bill_data.get('customer_info'), dict) else {}
    cd = bill_data.get('customer_details') if isinstance(bill_data.get('customer_details'), dict) else {}
    mobile = _scalar(ci, 'customerMobile', 'customer_mobile') or _scalar(cd, 'Mobile Number', 'mobile')

    if mode == 'cash':
        return 'Cash Payment'

    if mode in ('upi', 'bharat qr'):
        vpa = _resolve_vpa(bill_data=bill_data)
        return vpa

    if mode in ('debit card', 'credit card'):
        last4, issuer = _card_last4_issuer(bill_data=bill_data)
        if last4 and issuer:
            return f'{last4}|{issuer}'
        return ''

    if mode == 'wallet':
        wallet_name = _scalar(cd, 'Wallet Name', 'wallet_name') or 'Wallet'
        return f'{wallet_name}|{mobile}' if mobile else wallet_name

    if mode == 'aeps':
        aadhaar = extract_identity(bill_data=bill_data)
        last4 = ''
        if aadhaar[0] == 'Aadhaar' and len(aadhaar[1]) >= 4:
            last4 = aadhaar[1][-4:]
        else:
            last4 = _scalar(cd, 'Aadhaar Last4', 'aadhaar_last4')
        iin = _scalar(cd, 'IIN', 'iin') or _scalar(bill_data, 'iin', 'IIN')
        if last4 and iin:
            return f'{last4}|{iin}'
        return ''

    if mode == 'ussd':
        return 'USSD Payment'

    if mode in ('internet banking', 'neft', 'imps'):
        if payment_ref:
            return f'{payment_ref}|{payment_ref}'
        return ''

    if payment_ref:
        return f'{payment_ref}|{payment_ref}'
    return ''


def build_mode_specific_tags(*, payment_mode: str, bill_data: dict) -> list[dict]:
    mode = _norm_mode(payment_mode)
    rows: list[dict] = []

    if mode == 'cash':
        remarks = (
            _scalar(bill_data, 'remarks', 'Remarks')
            or _scalar(
                bill_data.get('customer_details') if isinstance(bill_data.get('customer_details'), dict) else {},
                'Remarks',
                'remarks',
            )
            or 'Received'
        )
        rows.append({'infoName': 'Remarks', 'infoValue': remarks})
        return rows

    if mode in ('upi', 'bharat qr'):
        vpa = _resolve_vpa(bill_data=bill_data)
        if vpa:
            rows.append({'infoName': 'VPA', 'infoValue': vpa})
        return rows

    if mode in ('debit card', 'credit card'):
        last4, _issuer = _card_last4_issuer(bill_data=bill_data)
        auth = _auth_code(bill_data=bill_data)
        if last4:
            rows.append({'infoName': 'CardNum', 'infoValue': last4})
        if auth:
            rows.append({'infoName': 'AuthCode', 'infoValue': auth})
        return rows

    return rows


def merge_payment_info_rows(existing: list | None, required: list | None) -> list[dict]:
    """Upsert by normalized infoName; required values win for matching keys."""
    out: list[dict] = []
    index: dict[str, int] = {}

    def _upsert(row: dict) -> None:
        if not isinstance(row, dict):
            return
        name = str(row.get('infoName') or row.get('info_name') or '').strip()
        if not name:
            return
        val = row.get('infoValue') if 'infoValue' in row else row.get('info_value')
        val_s = '' if val is None else str(val)
        key = _norm_info_name(name)
        payload = {'infoName': name, 'infoValue': val_s}
        if key in index:
            out[index[key]] = payload
        else:
            index[key] = len(out)
            out.append(payload)

    for row in existing or []:
        _upsert(row)
    for row in required or []:
        _upsert(row)
    return out


# paymentInfo must not carry these — BillAvenue wants them on customerInfo / top-level.
_PAYMENT_INFO_STRIP_NAMES = frozenset(
    {
        'remitter name',
        'remitter_name',
        'paymentrefid',
        'payment ref id',
        'pan',
        'aadhaar',
        'aadhar',
    }
)


def strip_identity_from_payment_info_rows(rows: list | None) -> list[dict]:
    """Drop Remitter Name / PaymentRefId / PAN / Aadhaar from paymentInfo rows."""
    out: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get('infoName') or row.get('info_name') or '').strip()
        if _norm_info_name(name) in _PAYMENT_INFO_STRIP_NAMES:
            continue
        out.append(row)
    return out


def normalize_customer_info_for_billavenue(customer_info: dict | None) -> dict:
    """
    Normalize customerInfo keys for BillAvenue XML.

    Frontend / APIs may send ``customerAadhaar``; BillAvenue expects historical
    spelling ``customerAdhaar``. Always prefer the pay-time identity values already
    on the dict (do not invent IDs).
    """
    out = dict(customer_info) if isinstance(customer_info, dict) else {}
    pan = _scalar(out, 'customerPan', 'customer_pan', 'PAN', 'pan')
    if pan:
        out['customerPan'] = pan.upper()

    aadhaar = _scalar(out, 'customerAdhaar', 'customer_adhaar', 'customerAadhaar', 'customer_aadhaar', 'Aadhaar', 'aadhaar')
    if aadhaar:
        digits = ''.join(ch for ch in aadhaar if ch.isdigit())
        value = digits or aadhaar
        out['customerAdhaar'] = value
        out.setdefault('customerAadhaar', value)
    return out


def apply_remitter_customer_info(
    customer_info: dict | None,
    *,
    remitter_name: str,
    bill_data: dict | None = None,
) -> dict:
    """
    Put REMITTER_NAME and customerPan/customerAdhaar under customerInfo (BillAvenue support).
    """
    out = normalize_customer_info_for_billavenue(customer_info)
    name = str(remitter_name or '').strip()
    if name:
        out['REMITTER_NAME'] = name
        if not str(out.get('customerName') or '').strip():
            out['customerName'] = name

    data = bill_data if isinstance(bill_data, dict) else {}
    # Merge identity from original bill_data.customer_info + outgoing customerInfo.
    prior_ci = data.get('customer_info') if isinstance(data.get('customer_info'), dict) else {}
    merged_for_id = dict(data)
    merged_for_id['customer_info'] = {**normalize_customer_info_for_billavenue(prior_ci), **out}
    id_kind, id_value = extract_identity(bill_data=merged_for_id)
    if id_kind == 'PAN' and id_value:
        out['customerPan'] = id_value
    elif id_kind == 'Aadhaar' and id_value:
        # BillAvenue XML uses historical spelling customerAdhaar.
        out['customerAdhaar'] = id_value
        out.setdefault('customerAadhaar', id_value)
    return normalize_customer_info_for_billavenue(out)


def build_remitter_payment_info_rows(
    *,
    remitter_name: str,
    payment_ref: str,
    payment_mode: str,
    bill_data: dict,
    amount=None,
    include_mode_label: bool = False,
) -> list[dict]:
    """
    paymentInfo rows for compliance mode: mode tags + Payment Account Info only.

    Remitter Name / PaymentRefId / PAN live on customerInfo and top-level paymentRefId
    (BillAvenue Technical Support, Oct 2026).
    """
    name = str(remitter_name or '').strip()
    if not name:
        raise TransactionFailed(MSG_REMITTER_NAME)

    ref = str(payment_ref or '').strip()
    if not ref:
        raise TransactionFailed(MSG_REMITTER_INCOMPLETE)

    high = is_high_value_amount(amount) if amount is not None else True

    mode_tags = build_mode_specific_tags(
        payment_mode=payment_mode,
        bill_data=bill_data if isinstance(bill_data, dict) else {},
    )
    account_info = derive_payment_account_info(
        payment_mode=payment_mode,
        bill_data=bill_data if isinstance(bill_data, dict) else {},
        correlation_ref=ref,
    )

    rows: list[dict] = []
    if mode_tags or high:
        rows.extend(mode_tags)
    if account_info or high:
        rows.append({'infoName': 'Payment Account Info', 'infoValue': account_info})

    if include_mode_label:
        from apps.integrations.bbps_client import _normalize_bbps_payment_mode

        rows.append(
            {
                'infoName': 'Payment mode',
                'infoValue': _normalize_bbps_payment_mode(payment_mode),
            }
        )

    return rows


def _info_map(rows: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        key = _norm_info_name(str(row.get('infoName') or ''))
        if not key:
            continue
        out[key] = str(row.get('infoValue') or '').strip()
    return out


def validate_high_value_remitter(
    *,
    amount,
    payment_mode: str,
    bill_data: dict,
    remitter_name: str = '',
    payment_ref: str = '',
    payment_info_rows: list[dict] | None = None,
) -> None:
    """
    Enforce BillAvenue high-value remitter rules when amount > 50000.
    Identity must be on customerInfo; paymentRefId is top-level (not paymentInfo).
    """
    if not is_high_value_amount(amount):
        return

    data = bill_data if isinstance(bill_data, dict) else {}
    name = str(remitter_name or '').strip()
    if not name:
        from apps.integrations.bbps_client import resolve_remitter_display_name

        name = resolve_remitter_display_name(data)
    ci = data.get('customer_info') if isinstance(data.get('customer_info'), dict) else {}
    if not name:
        name = str(ci.get('REMITTER_NAME') or '').strip()
    if not name:
        raise TransactionFailed(MSG_REMITTER_NAME)

    ref = str(payment_ref or '').strip() or str(data.get('request_id') or data.get('payment_ref_id') or '').strip()
    if not ref:
        raise TransactionFailed(MSG_REMITTER_INCOMPLETE)

    id_kind, id_value = extract_identity(bill_data=data)
    if not id_kind or not id_value:
        raise TransactionFailed(MSG_REMITTER_INCOMPLETE)

    mode = _norm_mode(payment_mode)
    account_info = derive_payment_account_info(
        payment_mode=payment_mode,
        bill_data=data,
        correlation_ref=ref,
    )
    if not account_info:
        if mode in ('upi', 'bharat qr'):
            raise TransactionFailed(MSG_VPA_INVALID)
        if mode in ('debit card', 'credit card'):
            raise TransactionFailed(MSG_CARD_DETAILS)
        raise TransactionFailed(MSG_ACCOUNT_INFO)

    if mode in ('upi', 'bharat qr') and '@' not in account_info:
        raise TransactionFailed(MSG_VPA_INVALID)

    if mode in ('debit card', 'credit card'):
        last4, issuer = _card_last4_issuer(bill_data=data)
        auth = _auth_code(bill_data=data)
        if not last4 or not issuer or not auth:
            raise TransactionFailed(MSG_CARD_DETAILS)

    rows = payment_info_rows
    if rows is None:
        rows = build_remitter_payment_info_rows(
            remitter_name=name,
            payment_ref=ref,
            payment_mode=payment_mode,
            bill_data=data,
            amount=amount,
        )
    info = _info_map(rows)

    if not info.get('payment account info'):
        raise TransactionFailed(MSG_ACCOUNT_INFO)

    if mode == 'cash' and not info.get('remarks'):
        raise TransactionFailed(MSG_ACCOUNT_INFO)
    if mode in ('upi', 'bharat qr') and not info.get('vpa'):
        raise TransactionFailed(MSG_VPA_INVALID)
    if mode in ('debit card', 'credit card'):
        if not info.get('cardnum') or not info.get('authcode'):
            raise TransactionFailed(MSG_CARD_DETAILS)
