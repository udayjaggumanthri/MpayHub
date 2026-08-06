"""
Central BillAvenue / BBPS error catalog.

Maps provider codes (E*, BFR*, VE*, BVR*, UM*, PP*, V5*) to safe, user-facing
messages. Never returns raw JSON dumps to callers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BbpsErrorInfo:
    provider_code: str
    category: str
    user_message: str
    action_hint: str = ''
    retryable: bool = False
    app_code: str = 'BBPS_ERROR'


# Categories: input_validation | account | provider_config | duplicate_replay | network | gateway | unknown

_CATALOG: dict[str, BbpsErrorInfo] = {
    # Fetch / payment input & account
    'E135': BbpsErrorInfo(
        'E135',
        'input_validation',
        'Check the highlighted fields — a required detail is missing or does not match what this biller expects.',
        'Verify each field label matches the biller form, then try Fetch Bill again.',
        False,
        'BBPS_INPUT_INVALID',
    ),
    'E092': BbpsErrorInfo(
        'E092',
        'input_validation',
        'Remitter details are missing. Update profile name and fetch bill again before payment.',
        'Ensure your profile has a full name, then fetch the bill again.',
        False,
        'BBPS_PAY_REMITTER',
    ),
    'E077': BbpsErrorInfo(
        'E077',
        'provider_config',
        'Selected payment mode is not valid for the initiating channel. Try Cash on AGT, or fetch the bill again after changing the method.',
        'Change payment method or contact support if this keeps failing.',
        False,
        'BBPS_PAY_CHANNEL',
    ),
    'E078': BbpsErrorInfo(
        'E078',
        'provider_config',
        'This biller does not accept the selected channel at the provider. '
        'Use Cash on the Agent (AGT) channel, fetch the bill again, then pay—or contact support if this continues.',
        'Change payment method or contact support if this keeps failing.',
        False,
        'BBPS_PAY_CHANNEL',
    ),
    'E0378': BbpsErrorInfo(
        'E0378',
        'provider_config',
        'Selected payment mode is not valid for the initiating channel. Try Cash on AGT, or fetch the bill again after changing the method.',
        '',
        False,
        'BBPS_PAY_CHANNEL',
    ),
    'E204': BbpsErrorInfo(
        'E204',
        'duplicate_replay',
        'This fetch reference is already consumed. Fetch the bill again before retrying payment.',
        'Tap Fetch Bill again, then pay immediately.',
        True,
        'BBPS_PAY_REF_USED',
    ),
    'E210': BbpsErrorInfo(
        'E210',
        'duplicate_replay',
        'Fetch reference is not valid anymore. Please fetch the bill again and retry payment.',
        'Tap Fetch Bill again, then pay.',
        True,
        'BBPS_PAY_REF_EXPIRED',
    ),
    'E211': BbpsErrorInfo(
        'E211',
        'duplicate_replay',
        'The bill snapshot sent to BillAvenue did not match your last successful fetch (billerResponse mismatch). '
        'Fetch the bill again, then pay immediately without changing amount, inputs, or plan selection.',
        'Fetch again and pay without editing fields.',
        True,
        'BBPS_PAY_SNAPSHOT',
    ),
    'E212': BbpsErrorInfo(
        'E212',
        'duplicate_replay',
        'Extra bill details from the provider (additionalInfo) did not match this payment. '
        'Fetch the bill again and pay immediately without changing tags, amount, or plan selection.',
        'Fetch again and pay without editing fields.',
        True,
        'BBPS_PAY_ADDITIONAL_INFO',
    ),
    'UM001': BbpsErrorInfo(
        'UM001',
        'input_validation',
        'BillAvenue rejected the request format for this biller. Required fields may be missing or incorrectly named.',
        'Re-select the biller, re-enter details carefully, then retry.',
        False,
        'BBPS_FETCH_FORMAT',
    ),
    'BFR001': BbpsErrorInfo(
        'BFR001',
        'account',
        'Customer account details are invalid. Please verify the entered account fields.',
        'Double-check account / consumer number and try again.',
        False,
        'BBPS_FETCH_ACCOUNT',
    ),
    'BFR004': BbpsErrorInfo(
        'BFR004',
        'account',
        'No bill is currently due for this account.',
        'Try again later or confirm the account with the biller.',
        False,
        'BBPS_FETCH_NO_DUE',
    ),
    'BFR006': BbpsErrorInfo(
        'BFR006',
        'account',
        'Unable to fetch bill for this account right now.',
        'Verify account details or retry shortly.',
        True,
        'BBPS_FETCH_ACCOUNT',
    ),
    'BRP046': BbpsErrorInfo(
        'BRP046',
        'provider_config',
        'This biller supports QuickPay only. Bill fetch is not required; proceed with QuickPay payment.',
        'Enter amount and continue to pay without fetching.',
        False,
        'BBPS_FETCH_QUICKPAY_ONLY',
    ),
    # BillAvenue validation (VE) / NPCI (BVR)
    'VE001': BbpsErrorInfo('VE001', 'provider_config', 'Agent ID is required. Configure it in BillAvenue Settings.', '', False, 'BBPS_AGENT'),
    'VE002': BbpsErrorInfo('VE002', 'provider_config', 'Agent ID format is invalid. Update it in BillAvenue Settings.', '', False, 'BBPS_AGENT'),
    'VE003': BbpsErrorInfo(
        'VE003',
        'provider_config',
        'BillAvenue rejected the Agent ID for this live environment (VE003). '
        'Open BillAvenue Settings → edit the live environment → set the correct Production Agent ID from your BillAvenue pack, then retry.',
        'Update the live environment Agent ID, then retry.',
        False,
        'BBPS_AGENT',
    ),
    'VE004': BbpsErrorInfo('VE004', 'input_validation', 'Biller ID is required.', '', False, 'BBPS_INPUT_INVALID'),
    'VE005': BbpsErrorInfo('VE005', 'input_validation', 'Biller ID format is invalid.', '', False, 'BBPS_INPUT_INVALID'),
    'VE006': BbpsErrorInfo('VE006', 'input_validation', 'Biller ID is invalid for this environment.', '', False, 'BBPS_INPUT_INVALID'),
    'VE007': BbpsErrorInfo('VE007', 'input_validation', 'A required customer field name is missing.', 'Re-select the biller and fill all required fields.', False, 'BBPS_INPUT_INVALID'),
    'VE008': BbpsErrorInfo('VE008', 'input_validation', 'A required customer field value is missing.', 'Fill all required fields marked with *.', False, 'BBPS_INPUT_INVALID'),
    'VE009': BbpsErrorInfo('VE009', 'input_validation', 'A field is shorter than this biller allows.', 'Check the length hint under each field.', False, 'BBPS_INPUT_INVALID'),
    'VE010': BbpsErrorInfo('VE010', 'input_validation', 'A field is longer than this biller allows.', 'Shorten the value to match the field hint.', False, 'BBPS_INPUT_INVALID'),
    'VE011': BbpsErrorInfo('VE011', 'input_validation', 'A field has the wrong data type (for example digits vs letters).', 'Use the format shown under the field.', False, 'BBPS_INPUT_INVALID'),
    'VE012': BbpsErrorInfo('VE012', 'input_validation', 'Customer input does not match what this biller expects.', 'Re-check each field against the hints.', False, 'BBPS_INPUT_INVALID'),
    # BillAvenue validate often returns VE013 with complianceReason "Mandatory Input Parameter Not Present or mismatch"
    # (same user meaning as E135). Real duplicate request ids typically use PP003 / E204.
    'VE013': BbpsErrorInfo(
        'VE013',
        'input_validation',
        'Check the highlighted fields — a required detail is missing or does not match what this biller expects.',
        'Select Circle from the list, enter Mobile Number, select a plan when shown, then try again.',
        False,
        'BBPS_INPUT_INVALID',
    ),
    'RPD053': BbpsErrorInfo(
        'RPD053',
        'input_validation',
        'Plan Id is not valid. Select a plan from the list for this biller.',
        'Choose Circle and Mobile Number, load plans, select a plan, then validate again.',
        False,
        'BBPS_PLAN',
    ),
    'BVR001': BbpsErrorInfo('BVR001', 'account', 'Incorrect / invalid customer account.', 'Verify account details with the customer.', False, 'BBPS_FETCH_ACCOUNT'),
    'BVR002': BbpsErrorInfo('BVR002', 'input_validation', 'Invalid combination of customer parameters.', 'Check all fields together match the biller rules.', False, 'BBPS_INPUT_INVALID'),
    'BVR003': BbpsErrorInfo('BVR003', 'account', 'Recharge amount does not exist for this biller.', 'Choose a valid plan or amount.', False, 'BBPS_PLAN'),
    # Gateway / encryption
    'PP001': BbpsErrorInfo('PP001', 'gateway', 'BillAvenue authentication failed. Check access credentials.', '', False, 'BBPS_AUTH'),
    'PP002': BbpsErrorInfo('PP002', 'gateway', 'Invalid encrypted request to BillAvenue.', 'Check Working Key, IV, and crypto profile (UAT PI39: md5 + hex).', False, 'BBPS_AUTH'),
    'DE001': BbpsErrorInfo(
        'DE001',
        'gateway',
        'Invalid encrypted request to BillAvenue (DE001). Working Key or IV may be missing or wrong for this environment.',
        'Open BillAvenue Settings → select UAT or Production → save Working Key and IV under Encrypted secrets.',
        False,
        'BBPS_AUTH',
    ),
    'PP003': BbpsErrorInfo('PP003', 'duplicate_replay', 'Duplicate request id rejected by BillAvenue.', 'Retry with a fresh fetch.', True, 'BBPS_DUP_REQUEST'),
    'PP004': BbpsErrorInfo('PP004', 'gateway', 'BillAvenue internal error. Please retry shortly.', '', True, 'BBPS_GATEWAY'),
    'PP005': BbpsErrorInfo('PP005', 'gateway', 'No data found from BillAvenue for this request.', '', True, 'BBPS_GATEWAY'),
    # Complaints
    'V5001': BbpsErrorInfo(
        'V5001',
        'input_validation',
        'Invalid B-Connect Transaction ID. Use the CC... reference shown on receipt/success screen.',
        '',
        False,
        'BBPS_COMPLAINT',
    ),
    'V5004': BbpsErrorInfo(
        'V5004',
        'input_validation',
        'Complaint description was rejected by provider. Please retry with a clear issue summary.',
        '',
        False,
        'BBPS_COMPLAINT',
    ),
}


_CODE_RE = re.compile(
    r'\b((?:E|BFR|BRP|VE|BVR|UM|PP|V|AE)\d{2,4})\b',
    re.IGNORECASE,
)
_JSON_ERR_RE = re.compile(r'\{\s*"errorCode"\s*:\s*"([^"]+)"\s*,\s*"errorMessage"\s*:\s*"([^"]*)"', re.I)
_JSON_ERR_RE2 = re.compile(r'\{\s*"errorMessage"\s*:\s*"([^"]*)"\s*,\s*"errorCode"\s*:\s*"([^"]+)"', re.I)
_MSG_ONLY_RE = re.compile(r'"errorMessage"\s*:\s*"([^"]+)"', re.I)


def _looks_like_json_blob(text: str) -> bool:
    t = (text or '').strip()
    return t.startswith('{') or '"errorCode"' in t or '"errorMessage"' in t


def _extract_code_and_provider_message(raw: str) -> tuple[str, str]:
    text = str(raw or '').strip()
    if not text:
        return '', ''

    m = _JSON_ERR_RE.search(text)
    if m:
        return m.group(1).strip().upper(), m.group(2).strip()
    m2 = _JSON_ERR_RE2.search(text)
    if m2:
        return m2.group(2).strip().upper(), m2.group(1).strip()

    # code=200 (VE003 — Agent ID invalid) or code=204 ({...})
    m3 = re.search(r'code=\S+\s*\((.+)\)\s*$', text, re.I | re.S)
    if m3:
        inner = m3.group(1).strip()
        code_m = _CODE_RE.search(inner)
        if '"errorCode"' in inner or inner.startswith('{'):
            c, msg = _extract_code_and_provider_message(inner)
            if c or msg:
                return c, msg
        if '—' in inner or ' - ' in inner:
            parts = re.split(r'\s*[—\-]\s*', inner, maxsplit=1)
            if len(parts) == 2 and _CODE_RE.match(parts[0].strip()):
                return parts[0].strip().upper(), parts[1].strip()
        if code_m:
            return code_m.group(1).upper(), inner

    code_m = _CODE_RE.search(text)
    code = code_m.group(1).upper() if code_m else ''
    msg_m = _MSG_ONLY_RE.search(text)
    msg = msg_m.group(1).strip() if msg_m else ''
    return code, msg


def _series_fallback(code: str, provider_msg: str) -> BbpsErrorInfo | None:
    c = (code or '').upper()
    if not c:
        return None
    if c.startswith('BFR'):
        return BbpsErrorInfo(
            c,
            'account',
            provider_msg or 'Unable to fetch bill for this account right now.',
            'Verify account details or retry shortly.',
            True,
            'BBPS_FETCH_ACCOUNT',
        )
    if c.startswith('VE') or c.startswith('BVR'):
        return BbpsErrorInfo(
            c,
            'input_validation',
            provider_msg or 'Customer input does not match biller rules.',
            'Check required fields and formats.',
            False,
            'BBPS_INPUT_INVALID',
        )
    if re.match(r'^E1\d{2}$', c):
        return BbpsErrorInfo(
            c,
            'input_validation',
            provider_msg
            or 'Check the highlighted fields — a required detail is missing or does not match what this biller expects.',
            'Verify each field, then retry.',
            False,
            'BBPS_INPUT_INVALID',
        )
    if c.startswith('PP'):
        return BbpsErrorInfo(c, 'gateway', provider_msg or 'BillAvenue gateway error. Please retry.', '', True, 'BBPS_GATEWAY')
    if c.startswith('V5'):
        return BbpsErrorInfo(c, 'input_validation', provider_msg or 'Complaint request was rejected.', '', False, 'BBPS_COMPLAINT')
    return None


def _network_info(raw: str, endpoint: str) -> BbpsErrorInfo | None:
    low = (raw or '').lower()
    if 'timeout' in low or 'timed out' in low:
        if endpoint in ('plan_pull', 'plan'):
            return BbpsErrorInfo(
                'TIMEOUT',
                'network',
                'Plan service response timed out. Please retry. If this continues, verify BillAvenue timeout settings.',
                'Retry in a few seconds.',
                True,
                'BBPS_PLAN_TIMEOUT',
            )
        if endpoint in ('bill_fetch', 'fetch'):
            return BbpsErrorInfo(
                'TIMEOUT',
                'network',
                'Provider response timed out. Please retry in a few seconds.',
                'Retry shortly.',
                True,
                'BBPS_FETCH_TIMEOUT',
            )
        return BbpsErrorInfo(
            'TIMEOUT',
            'network',
            'The payment provider took too long to respond. Please try again in a few seconds.',
            'Retry shortly.',
            True,
            'BBPS_TIMEOUT',
        )
    if 'connection error' in low or 'max retries exceeded' in low or 'name or service not known' in low:
        if endpoint in ('plan_pull', 'plan'):
            return BbpsErrorInfo(
                'TRANSPORT',
                'network',
                'Unable to reach plan service right now. Please retry and verify provider connectivity.',
                '',
                True,
                'BBPS_PLAN_TRANSPORT',
            )
        return BbpsErrorInfo(
            'TRANSPORT',
            'network',
            'Provider network is temporarily unavailable. Please retry shortly.',
            '',
            True,
            'BBPS_TRANSPORT',
        )
    return None


def _complaint_special(raw: str) -> BbpsErrorInfo | None:
    low = (raw or '').lower()
    if 'complaint_register' not in low and 'complaint' not in low:
        return None
    if 'code=001' in low and (
        'unable to raise a new ticket' in low
        or ('unable to raise' in low and 'ticket' in low)
        or 'the ticket is already' in low
        or 'ticket is already' in low
        or 'already open' in low
        or 'existing ticket' in low
        or 'complaint is already' in low
    ):
        return BbpsErrorInfo(
            '001',
            'duplicate_replay',
            'BillAvenue indicates a complaint ticket may already exist for this transaction, or another rule prevents '
            'opening a new ticket. Use Complaint Tracking for this B-Connect transaction ID, or contact support with '
            'your transaction ID and the BillAvenue request ID shown on this screen.',
            '',
            False,
            'BBPS_COMPLAINT',
        )
    if 'code=001' in low and ('unable to process' in low or 'unable to process your request' in low):
        return BbpsErrorInfo(
            '001',
            'unknown',
            'BillAvenue did not accept this complaint request for the given B-Connect (CC) transaction ID. '
            'Confirm the ID from the receipt, then retry or use Complaint Tracking.',
            '',
            False,
            'BBPS_COMPLAINT',
        )
    if 'code=205' in low and 'failure' in low and 'v500' not in low:
        return BbpsErrorInfo(
            '205',
            'gateway',
            'BillAvenue returned error 205 for complaint registration. '
            'Complaint service may be unavailable for this profile right now. Please retry later or contact support.',
            '',
            True,
            'BBPS_COMPLAINT',
        )
    if 'code=205' in low or 'entitlement' in low:
        if 'plan' in low:
            return BbpsErrorInfo(
                '205',
                'provider_config',
                'Plan pull is not enabled for this BillAvenue profile. Check agent/profile entitlement in admin.',
                '',
                False,
                'BBPS_PLAN',
            )
    return None


def _sanitize_fallback_message(raw: str, provider_msg: str) -> str:
    """Never return raw JSON blobs to the UI."""
    if provider_msg and not _looks_like_json_blob(provider_msg):
        return provider_msg
    text = str(raw or '').strip()
    if not text:
        return 'Something went wrong with this bill payment request. Please try again.'
    if _looks_like_json_blob(text):
        m = _MSG_ONLY_RE.search(text)
        if m and m.group(1).strip():
            return m.group(1).strip()
        return 'The bill payment provider rejected this request. Please verify your details and try again.'
    # Strip "BillAvenue API failed (...)" wrapper when leftover
    m = re.search(r'code=\S+\s*\((.+)\)\s*$', text, re.I | re.S)
    if m:
        inner = m.group(1).strip()
        if not _looks_like_json_blob(inner):
            return inner
    if text.lower().startswith('billavenue api failed'):
        return 'The bill payment provider rejected this request. Please verify your details and try again.'
    return text


def resolve_bbps_error(raw_text: str, *, endpoint: str = '') -> BbpsErrorInfo:
    """
    Resolve any BillAvenue / BBPS exception string into a structured, UI-safe error.
    """
    raw = str(raw_text or '').strip()
    ep = str(endpoint or '').strip().lower()

    net = _network_info(raw, ep)
    if net:
        return net

    # Plan entitlement heuristic
    low = raw.lower()
    if ep in ('plan_pull', 'plan') and ('code=205' in low or 'entitlement' in low):
        return BbpsErrorInfo(
            '205',
            'provider_config',
            'Plan pull is not enabled for this BillAvenue profile. Ask BillAvenue to enable Plan MDM (extPlanMDM) for your institute.',
            '',
            False,
            'BBPS_PLAN',
        )
    if ep in ('plan_pull', 'plan') and 'pp002' in low and 'invalid enc' in low:
        return BbpsErrorInfo(
            'PP002',
            'provider_config',
            'BillAvenue rejected the plan-pull request (PP002). Confirm Plan MDM is enabled for this institute, or re-check working key / IV with BillAvenue support.',
            '',
            False,
            'BBPS_PLAN',
        )
    if ep in ('plan_pull', 'plan') and 'pp002' in low:
        return BbpsErrorInfo('PP002', 'gateway', 'No plan data is available for this biller right now.', '', True, 'BBPS_PLAN')
    if ep in ('plan_pull', 'plan') and 'agentid is required' in low:
        return BbpsErrorInfo(
            'VE001',
            'provider_config',
            'Plan pull requires an active BillAvenue agent profile. Configure agentId in admin settings.',
            '',
            False,
            'BBPS_AGENT',
        )

    special = _complaint_special(raw)
    if special:
        return special

    if 'agent_device_info missing required field' in low:
        return BbpsErrorInfo(
            '',
            'provider_config',
            'Selected payment method is not available for this biller in the current terminal flow. '
            'Please choose another payment method.',
            '',
            False,
            'BBPS_PAY_CHANNEL',
        )
    if 'de001' in low or ('invalid enc' in low and 'request' in low):
        return _CATALOG['DE001']
    if 'invalid for payment channel' in low or 'errorcode": "e077' in low:
        return _CATALOG['E077']
    # Phrase heuristics before generic code extract (preserve existing UX copy)
    if 'request id is already been used' in low or ('already been used' in low and 'e204' in low):
        return _CATALOG['E204']
    if 'agent id invalid' in low or 'agentid invalid' in low:
        return _CATALOG['VE003']
    if 'only quickpay permitted' in low or 'quickpay permitted' in low:
        return _CATALOG['BRP046']
    if 'no bill due' in low:
        return _CATALOG['BFR004']
    if 'invalid customer account' in low:
        return _CATALOG['BFR001']
    if 'remitter name required' in low:
        return _CATALOG['E092']
    if 'additionalinfo value mismatch' in low:
        return _CATALOG['E212']
    if 'billerresponse value mismatch' in low:
        return _CATALOG['E211']
    if 'no fetch data found for given ref id' in low:
        return _CATALOG['E210']
    if 'payment channel' in low and 'invalid' in low:
        return _CATALOG['E078']
    # Live BillAvenue validate: VE013 + this reason means missing/mismatched MDM inputs (not a duplicate id).
    if 'mandatory input parameter' in low:
        return _CATALOG['E135']

    code, provider_msg = _extract_code_and_provider_message(raw)
    if code and code in _CATALOG:
        info = _CATALOG[code]
        pml = (provider_msg or '').lower()
        if code == 'VE013' and ('duplicate' in pml or 'already' in pml):
            return BbpsErrorInfo(
                'VE013',
                'duplicate_replay',
                'Duplicate request ID. Please fetch the bill again.',
                'Retry with a fresh Validate / Fetch.',
                True,
                'BBPS_DUP_REQUEST',
            )
        if 'mandatory input parameter' in pml:
            return _CATALOG['E135']
        return info

    series = _series_fallback(code, provider_msg)
    if series:
        return series

    msg = _sanitize_fallback_message(raw, provider_msg)
    return BbpsErrorInfo(
        code or '',
        'unknown',
        msg,
        'If this continues, contact support with the reference id shown on screen.',
        False,
        'BBPS_ERROR',
    )


def provider_code_from_exception(exc: Any) -> str:
    code = str(getattr(exc, 'provider_code', '') or '').strip().upper()
    if code:
        return code
    c, _ = _extract_code_and_provider_message(str(exc or ''))
    return c
