"""
Default Fingpay endpoint path maps — admin-overridable via AepsProviderConfig.endpoints_json.

Paths are relative to the matching base URL:
- onboarding_* → onboarding_base_url (…/fpaepsweb)
- ekyc_* → ekyc_base_url
- aeps_* / 2fa / product / ack → aeps_base_url (host root; paths include fpaepsservice/…)
- recon → recon_base_url
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

# No literal here on purpose: the egress address is a property of wherever this
# host is deployed, so it is detected at runtime (see fingpay.netinfo) and only
# falls back to the admin-configured provider value.
DEFAULT_EGRESS_IP = ''

# Encrypted PHP paths (uat/prod default when onboarding_api_style=php)
ENCRYPTED_PHP_ENDPOINTS: dict[str, str] = {
    'onboarding_create_java': '/api/onboarding/merchant/creation/v2',
    'onboarding_create_php': '/api/onboarding/merchant/php/creation/v2',
    'onboarding_create_simple': '/api/onboarding/merchant/simple/creation/v2',
    'onboarding_states': '/api/onboarding/getstates',
    'onboarding_company_types': '/api/onboarding/get/companyType/master',
    'ekyc_send_otp': 'fpekyc/api/ekyc/merchant/php/sendotp',
    'ekyc_validate_otp': 'fpekyc/api/ekyc/merchant/php/validateotp',
    'ekyc_resend_otp': 'fpekyc/api/ekyc/merchant/php/resendotp',
    'ekyc_biometric': 'fpekyc/api/ekyc/merchant/php/biometric',
    'ekyc_status': 'fpekyc/api/ekyc/status/check',
    'twofa_validate': 'fpaepsservice/auth/tfauth/merchant/php/validate/aadhar',
    'cw': 'fpaepsservice/api/cashWithdrawal/merchant/php/withdrawal',
    'be': 'fpaepsservice/api/balanceInquiry/merchant/php/getBalance',
    'ms': 'fpaepsservice/api/miniStatement/merchant/php/statement',
    'ap': 'fpaepsservice/api/aadhaarPay/merchant/php/pay',
    'cd': 'fpaepsservice/api/CashDeposit/merchant/php/deposit',
    'cd_otp_generate': 'fpaepsservice/api/CashDeposit/merchant/php/generate/otp',
    'cd_otp_validate': 'fpaepsservice/api/CashDeposit/merchant/php/validate/otp',
    'cd_otp_txn': 'fpaepsservice/api/CashDeposit/merchant/php/transaction',
    'ack_cw': 'fpaepsservice/api/cashWithdrawal/merchant/php/acknowledgement',
    'ack_cd': 'fpaepsservice/api/CashDeposit/merchant/deposit/acknowledgement',
    'ack_cd_otp': 'fpaepsservice/api/CashDeposit/otp/merchant/acknowledgement',
    'status_cw': 'api/auth/merchantInfo/statusCheckV2/merchantLoginId/cashWithdrawal/v2',
    'status_cd': 'api/auth/merchantInfo/statusCheckV2/merchantLoginId/cashDeposit',
    'status_cd_otp': 'api/auth/merchantInfo/statusCheck/cashDepositWithOtp',
    'status_ap': 'api/auth/merchantInfo/statusCheckV3/aadhaarPay/merchantLoginId',
    'banks_aeps': 'fpaepsservice/api/bankdata/bank/details',
    'banks_aadhaar_pay': 'fpaepsservice/api/bankdata/bank/aadharpay',
    'recon': 'fpcollectservice_uat/api/threeway/aggregators',
}

# Encrypted Java/.NET paths (when onboarding_api_style=java for products too)
ENCRYPTED_JAVA_ENDPOINTS: dict[str, str] = {
    **ENCRYPTED_PHP_ENDPOINTS,
    'ekyc_send_otp': 'fpekyc/api/ekyc/merchant/sendotp',
    'ekyc_validate_otp': 'fpekyc/api/ekyc/merchant/validateotp',
    'ekyc_resend_otp': 'fpekyc/api/ekyc/merchant/resendotp',
    'ekyc_biometric': 'fpekyc/api/ekyc/merchant/biometric',
    'twofa_validate': 'fpaepsservice/auth/tfauth/merchant/validate/aadhar',
    'cw': 'fpaepsservice/api/cashWithdrawal/merchant/withdrawal',
    'be': 'fpaepsservice/api/balanceInquiry/merchant/getBalance',
    'ms': 'fpaepsservice/api/miniStatement/merchant/statement',
    'ap': 'fpaepsservice/api/aadhaarPay/merchant/pay',
    'cd': 'fpaepsservice/api/CashDeposit/merchant/deposit',
    'cd_otp_generate': 'fpaepsservice/api/CashDeposit/merchant/generate/otp',
    'cd_otp_validate': 'fpaepsservice/api/CashDeposit/merchant/validate/otp',
    'cd_otp_txn': 'fpaepsservice/api/CashDeposit/merchant/transaction',
    'ack_cw': 'fpaepsservice/api/cashWithdrawal/merchant/acknowledgement',
}

# Simple API plain-JSON paths
SIMPLE_ENDPOINTS: dict[str, str] = {
    **ENCRYPTED_PHP_ENDPOINTS,
    'onboarding_create_simple': '/api/onboarding/merchant/simple/creation/v2',
    'ekyc_send_otp': 'fpekyc/api/ekyc/merchant/v1/sendotp',
    'ekyc_validate_otp': 'fpekyc/api/ekyc/merchant/v1/validateotp',
    'ekyc_resend_otp': 'fpekyc/api/ekyc/merchant/v1/resendotp',
    'ekyc_biometric': 'fpekyc/api/ekyc/merchant/v1/biometric',
    'twofa_validate': 'fpaepsservice/auth/tfauth/merchant/simple/validate/aadhar',
    'cw': 'fpaepsservice/api/cashWithdrawal/merchant/v2/withdrawal',
    'be': 'fpaepsservice/api/balanceInquiry/merchant/v2/getBalance',
    'ms': 'fpaepsservice/api/miniStatement/merchant/v2/statement',
    'ap': 'fpaepsservice/api/aadhaarPay/merchant/v2/pay',
    'cd': 'fpaepsservice/api/CashDeposit/merchant/v2/deposit',
    'cd_otp_generate': 'fpaepsservice/api/CashDeposit/merchant/v2/generate/otp',
    'cd_otp_validate': 'fpaepsservice/api/CashDeposit/merchant/v2/validate/otp',
    'cd_otp_txn': 'fpaepsservice/api/CashDeposit/merchant/v2/transaction',
    'ack_cw': 'fpaepsservice/api/cashWithdrawal/merchant/v2/acknowledgement',
}

URL_PRESETS: dict[str, dict[str, str]] = {
    'uat': {
        'onboarding_base_url': 'https://fpuat.tapits.in/fpaepsweb',
        'ekyc_base_url': 'https://fpekyc.tapits.in',
        'aeps_base_url': 'https://fpuat.tapits.in',
        'recon_base_url': 'https://fpuat.tapits.in',
        'bank_list_url': 'https://fpuat.tapits.in/fpaepsservice/api/bankdata/bank/details',
        'aadhaar_pay_bank_list_url': 'https://fpuat.tapits.in/fpaepsservice/api/bankdata/bank/aadharpay',
    },
    'prod': {
        'onboarding_base_url': 'https://fingpayap.tapits.in/fpaepsweb',
        'ekyc_base_url': 'https://fpekyc.tapits.in',
        'aeps_base_url': 'https://fingpayap.tapits.in',
        'recon_base_url': '',
        'bank_list_url': 'https://fingpayap.tapits.in/fpaepsservice/api/bankdata/bank/details',
        'aadhaar_pay_bank_list_url': 'https://fingpayap.tapits.in/fpaepsservice/api/bankdata/bank/aadharpay',
    },
    'simple': {
        # Tapits (14 Aug 2026): Mini Statement + onboarding PIN reset use production
        # fingpayap only. Do not use fpuat for Simple txn APIs. eKYC stays on fpekyc.
        'onboarding_base_url': 'https://fingpayap.tapits.in/fpaepsweb',
        'ekyc_base_url': 'https://fpekyc.tapits.in',
        'aeps_base_url': 'https://fingpayap.tapits.in',
        'recon_base_url': 'https://fingpayap.tapits.in',
        'bank_list_url': 'https://fingpayap.tapits.in/fpaepsservice/api/bankdata/bank/details',
        'aadhaar_pay_bank_list_url': 'https://fingpayap.tapits.in/fpaepsservice/api/bankdata/bank/aadharpay',
    },
}

PRODUCT_PATH_KEYS = {
    'CW': 'cw',
    'BE': 'be',
    'MS': 'ms',
    'AP': 'ap',
    'CD': 'cd',
}

STATUS_PATH_KEYS = {
    'CW': 'status_cw',
    'BE': 'status_cw',
    'MS': 'status_cw',
    'AP': 'status_ap',
    'CD': 'status_cd',
    'CD_OTP': 'status_cd_otp',
}

ACK_PATH_KEYS = {
    'CW': 'ack_cw',
    'AP': 'ack_cw',
    'CD': 'ack_cd',
    'CD_OTP': 'ack_cd_otp',
}


def default_endpoints_for(*, environment: str, onboarding_api_style: str = 'php') -> dict[str, str]:
    env = (environment or 'prod').lower()
    if env == 'simple':
        return deepcopy(SIMPLE_ENDPOINTS)
    style = (onboarding_api_style or 'php').lower()
    if style == 'java':
        return deepcopy(ENCRYPTED_JAVA_ENDPOINTS)
    return deepcopy(ENCRYPTED_PHP_ENDPOINTS)


def merge_endpoints(stored: Any, *, environment: str, onboarding_api_style: str = 'php') -> dict[str, str]:
    base = default_endpoints_for(environment=environment, onboarding_api_style=onboarding_api_style)
    if isinstance(stored, dict) and stored:
        for k, v in stored.items():
            if v is not None and str(v).strip():
                base[str(k)] = str(v).strip()
    return base


def url_preset(environment: str) -> dict[str, str]:
    return deepcopy(URL_PRESETS.get((environment or 'prod').lower(), URL_PRESETS['prod']))


# Admin-facing labels for editable module endpoints (full URL or relative path)
ENDPOINT_FIELD_META: list[dict[str, str]] = [
    {'key': 'onboarding_create_simple', 'label': 'Onboarding create (Simple)', 'base': 'onboarding'},
    {'key': 'onboarding_create_java', 'label': 'Onboarding create (Java/.NET)', 'base': 'onboarding'},
    {'key': 'onboarding_create_php', 'label': 'Onboarding create (PHP)', 'base': 'onboarding'},
    {'key': 'onboarding_states', 'label': 'Get states', 'base': 'onboarding'},
    {'key': 'onboarding_company_types', 'label': 'Company types', 'base': 'onboarding'},
    {'key': 'ekyc_send_otp', 'label': 'eKYC send OTP', 'base': 'ekyc'},
    {'key': 'ekyc_validate_otp', 'label': 'eKYC validate OTP', 'base': 'ekyc'},
    {'key': 'ekyc_resend_otp', 'label': 'eKYC resend OTP', 'base': 'ekyc'},
    {'key': 'ekyc_biometric', 'label': 'eKYC biometric', 'base': 'ekyc'},
    {'key': 'ekyc_status', 'label': 'eKYC status check', 'base': 'ekyc'},
    {'key': 'twofa_validate', 'label': 'Daily 2FA validate', 'base': 'aeps'},
    {'key': 'cw', 'label': 'Cash withdrawal', 'base': 'aeps'},
    {'key': 'be', 'label': 'Balance enquiry', 'base': 'aeps'},
    {'key': 'ms', 'label': 'Mini statement', 'base': 'aeps'},
    {'key': 'ap', 'label': 'Aadhaar Pay', 'base': 'aeps'},
    {'key': 'cd', 'label': 'Cash deposit', 'base': 'aeps'},
    {'key': 'cd_otp_generate', 'label': 'CD OTP generate', 'base': 'aeps'},
    {'key': 'cd_otp_validate', 'label': 'CD OTP validate', 'base': 'aeps'},
    {'key': 'cd_otp_txn', 'label': 'CD OTP transaction', 'base': 'aeps'},
    {'key': 'ack_cw', 'label': 'Ack cash withdrawal', 'base': 'aeps'},
    {'key': 'ack_cd', 'label': 'Ack cash deposit', 'base': 'aeps'},
    {'key': 'ack_cd_otp', 'label': 'Ack CD OTP', 'base': 'aeps'},
    {'key': 'status_cw', 'label': 'Status check CW', 'base': 'onboarding'},
    {'key': 'status_cd', 'label': 'Status check CD', 'base': 'onboarding'},
    {'key': 'status_cd_otp', 'label': 'Status check CD OTP', 'base': 'onboarding'},
    {'key': 'status_ap', 'label': 'Status check Aadhaar Pay', 'base': 'onboarding'},
    {'key': 'banks_aeps', 'label': 'Bank list (AEPS)', 'base': 'aeps'},
    {'key': 'banks_aadhaar_pay', 'label': 'Bank list (Aadhaar Pay)', 'base': 'aeps'},
    {'key': 'recon', 'label': '3-way recon', 'base': 'recon'},
]


def expand_endpoints_to_full_urls(
    endpoints: dict[str, str] | None,
    *,
    onboarding_base_url: str = '',
    ekyc_base_url: str = '',
    aeps_base_url: str = '',
    recon_base_url: str = '',
) -> dict[str, str]:
    """Turn relative endpoint paths into absolute URLs for admin editing."""
    bases = {
        'onboarding': (onboarding_base_url or '').rstrip('/'),
        'ekyc': (ekyc_base_url or '').rstrip('/'),
        'aeps': (aeps_base_url or '').rstrip('/'),
        'recon': (recon_base_url or aeps_base_url or '').rstrip('/'),
    }
    key_base = {m['key']: m['base'] for m in ENDPOINT_FIELD_META}
    out: dict[str, str] = {}
    for k, v in (endpoints or {}).items():
        path = str(v or '').strip()
        if not path:
            continue
        if path.startswith('http://') or path.startswith('https://'):
            out[k] = path
            continue
        base = bases.get(key_base.get(k, 'aeps'), '')
        if not base:
            out[k] = path
        elif path.startswith('/'):
            out[k] = f'{base}{path}'
        else:
            out[k] = f'{base}/{path}'
    return out
