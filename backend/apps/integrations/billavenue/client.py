import json
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import requests
from django.utils import timezone

from apps.integrations.billavenue.crypto import decrypt_payload_auto
from apps.integrations.billavenue.envelope import build_encrypted_envelope
from apps.integrations.billavenue.xml_request import (
    build_biller_info_plain_xml,
    build_bill_fetch_plain_xml,
    build_bill_pay_plain_xml,
    build_complaint_register_plain_xml,
    build_complaint_track_plain_xml,
    build_plan_pull_plain_xml,
)
from apps.integrations.billavenue.errors import (
    BillAvenueAuthError,
    BillAvenueClientError,
    BillAvenueTransportError,
    BillAvenueValidationError,
    exception_for_code,
)
from apps.integrations.billavenue.parsers import (
    extract_complaint_api_outcome_code,
    extract_element_outer_xml_from_plaintext,
    extract_response_code,
    normalize_decrypted_plaintext,
    parse_payload_text,
)
from apps.integrations.models import BillAvenueConfig
from apps.integrations.billavenue.registry import normalize_billavenue_mode
from apps.bbps.models import BbpsApiAuditLog

logger = logging.getLogger(__name__)


def _attach_billavenue_request_id(exc: BaseException, request_id: str) -> None:
    """Let upstream handlers read getattr(exc, 'billavenue_request_id', '') for support (e.g. BBPS complaints)."""
    try:
        setattr(exc, 'billavenue_request_id', str(request_id or '').strip())
    except Exception:
        pass


def _extract_enc_response_field(data: dict) -> str:
    """BillAvenue JSON keys vary by stack (encResponse, EncResponse, enc_response)."""
    if not isinstance(data, dict):
        return ''
    for key in ('encResponse', 'encresponse', 'EncResponse', 'ENC_RESPONSE', 'enc_response'):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    for k, v in data.items():
        if not isinstance(v, str) or not str(v).strip():
            continue
        lk = str(k).lower().replace('_', '')
        if lk == 'encresponse' or lk.endswith('encresponse') or lk == 'encresp':
            return str(v).strip()
    return ''


def _retry_parse_if_only_raw(normalized, plain: str):
    """If parse_payload_text fell back to {'raw': ...}, try JSON/XML recovery on the raw blob."""
    if not isinstance(normalized, dict) or set(normalized.keys()) != {'raw'}:
        return normalized
    inner = str(normalized.get('raw') or '').strip()
    if not inner:
        return normalized
    if inner.startswith('"'):
        try:
            unwrapped = json.loads(inner)
            if isinstance(unwrapped, str):
                inner = unwrapped.strip()
            elif isinstance(unwrapped, dict):
                return unwrapped
        except Exception:
            pass
    # Always re-parse raw (XML plaintext errors, JSON-in-string, etc.).
    retry = parse_payload_text(inner)
    if isinstance(retry, dict) and retry and set(retry.keys()) != {'raw'}:
        return retry
    if inner and inner != plain:
        retry2 = parse_payload_text(inner)
        if isinstance(retry2, dict) and retry2 and set(retry2.keys()) != {'raw'}:
            return retry2
    return normalized


def _normalized_text(normalized: dict) -> str:
    if not isinstance(normalized, dict):
        return str(normalized or '')
    raw = normalized.get('raw')
    if isinstance(raw, str) and raw.strip():
        return raw
    try:
        return json.dumps(normalized, ensure_ascii=False)
    except Exception:
        return str(normalized)


def _inner_complaint_response_blocks(normalized: dict) -> list:
    """Return dict bodies under complaintRegistrationResp / complaintTrackingResp (any key casing)."""
    if not isinstance(normalized, dict):
        return []
    out = []
    for k, v in normalized.items():
        lk = str(k).lower().replace('_', '')
        if lk in ('complaintregistrationresp', 'complainttrackingresp') and isinstance(v, dict):
            out.append(v)
    return out


def _extract_complaint_response_reason(normalized) -> str:
    """Walk nested complaint payloads for the human-readable provider reason (avoid truncating mid-sentence)."""
    if isinstance(normalized, dict):
        for block in _inner_complaint_response_blocks(normalized):
            for sk in (
                'complaintResponseReason',
                'ComplaintResponseReason',
                'responseReason',
                'ResponseReason',
                'errorMessage',
                'ErrorMessage',
            ):
                v = block.get(sk)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    if isinstance(normalized, dict):
        for key, val in normalized.items():
            lk = str(key).lower().replace('_', '')
            if lk == 'complaintresponsereason' and isinstance(val, str) and val.strip():
                return val.strip()
        for val in normalized.values():
            hit = _extract_complaint_response_reason(val)
            if hit:
                return hit
    elif isinstance(normalized, list):
        for it in normalized:
            hit = _extract_complaint_response_reason(it)
            if hit:
                return hit
    return ''


def _has_invalid_enc_request(normalized: dict) -> bool:
    text = _normalized_text(normalized).lower()
    return (
        'de001' in text
        or 'invalid enc request' in text
        or 'pp002' in text
    )


def _extract_error_block(normalized: dict) -> dict:
    """Extract top-level provider error details for audit/debug."""
    if not isinstance(normalized, dict):
        return {}
    code = ''
    message = ''
    err_info = normalized.get('errorInfo')
    if isinstance(err_info, dict):
        err_list = err_info.get('error')
        if isinstance(err_list, list) and err_list:
            first = err_list[0] if isinstance(err_list[0], dict) else {}
            code = str(first.get('errorCode') or '').strip()
            message = str(first.get('errorMessage') or '').strip()
        err = err_info.get('error')
        if isinstance(err, dict):
            code = str(err.get('errorCode') or '').strip()
            message = str(err.get('errorMessage') or '').strip()
    elif isinstance(err_info, list) and err_info:
        first = err_info[0] if isinstance(err_info[0], dict) else {}
        err = first.get('error') if isinstance(first, dict) else {}
        if isinstance(err, dict):
            code = str(err.get('errorCode') or '').strip()
            message = str(err.get('errorMessage') or '').strip()
    if not code and isinstance(normalized.get('errorCode'), str):
        code = str(normalized.get('errorCode') or '').strip()
    if not message and isinstance(normalized.get('errorMessage'), str):
        message = str(normalized.get('errorMessage') or '').strip()
    # BillAvenue validate/fetch often returns complianceCode / complianceReason instead of errorInfo.
    if not code:
        for ck in ('complianceCode', 'ComplianceCode', 'compliance_code'):
            v = normalized.get(ck)
            if isinstance(v, str) and v.strip():
                code = v.strip()
                break
    if not message:
        for mk in ('complianceReason', 'ComplianceReason', 'compliance_reason'):
            v = normalized.get(mk)
            if isinstance(v, str) and v.strip():
                message = v.strip()
                break
    if not code and not message:
        return {}
    return {'errorCode': code, 'errorMessage': message}


def _extract_error_block_deep(normalized: dict) -> dict:
    """Walk nested BillAvenue wrappers for the first errorCode/errorMessage block."""
    if not isinstance(normalized, dict):
        return {}
    direct = _extract_error_block(normalized)
    if direct.get('errorCode') or direct.get('errorMessage'):
        return direct
    for val in normalized.values():
        if isinstance(val, dict):
            hit = _extract_error_block_deep(val)
            if hit.get('errorCode') or hit.get('errorMessage'):
                return hit
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    hit = _extract_error_block_deep(item)
                    if hit.get('errorCode') or hit.get('errorMessage'):
                        return hit
    return {}


def _error_message_from_normalized(normalized: dict) -> str:
    """Extract provider error text from normalized payload for operator-facing diagnostics."""
    if not isinstance(normalized, dict):
        return ''

    blk = _extract_error_block_deep(normalized)
    code = str(blk.get('errorCode') or '').strip()
    message = str(blk.get('errorMessage') or '').strip()
    if code or message:
        if code and message:
            return f'{code} — {message}'
        return message or code

    def _pick(*keys: str) -> str:
        for key in keys:
            val = normalized.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
            for k, v in normalized.items():
                if str(k).lower() == key.lower() and isinstance(v, str) and v.strip():
                    return v.strip()
        return ''

    compliance = _pick('complianceReason', 'compliance_reason')
    reason = _pick('responseReason', 'response_reason')
    compliance_code = _pick('complianceCode', 'compliance_code')
    if compliance or reason:
        parts = []
        if compliance_code:
            parts.append(compliance_code)
        if compliance:
            parts.append(compliance)
        elif reason:
            parts.append(reason)
        return ' — '.join(parts) if len(parts) > 1 else (parts[0] if parts else '')

    for val in normalized.values():
        if isinstance(val, dict):
            nested = _error_message_from_normalized(val)
            if nested:
                return nested

    text_blob = _normalized_text(normalized)
    if not text_blob:
        return ''
    low = text_blob.lower()
    if 'invalid enc request' in low:
        return 'Invalid ENC request'
    if 'access denied' in low or 'unauthorized access detected' in low:
        return 'Access denied'
    # Never dump raw JSON containing errorCode into the exception suffix.
    if 'errorcode' in low or 'errormessage' in low or 'compliancereason' in low:
        return ''
    return ''


_ENDPOINTS_BY_KEY = {
    'biller_info': {
        'json': 'billpay/extMdmCntrl/mdmRequestNew/json',
        'xml': 'billpay/extMdmCntrl/mdmRequestNew/xml',
    },
    'bill_fetch': {
        'json': 'billpay/extBillCntrl/billFetchRequest/json',
        'xml': 'billpay/extBillCntrl/billFetchRequest/xml',
    },
    'bill_validate': {
        'json': 'billpay/extBillValCntrl/billValidationRequest/json',
        'xml': 'billpay/extBillValCntrl/billValidationRequest/xml',
    },
    'bill_pay': {
        'json': 'billpay/extBillPayCntrl/billPayRequest/json',
        'xml': 'billpay/extBillPayCntrl/billPayRequest/xml',
    },
    'txn_status': {
        # BillAvenue often uses lowercase for JSON status endpoint.
        'json': 'billpay/transactionstatus/fetchinfo/json',
        # PDF sometimes shows camel-case for XML status endpoint.
        'xml': 'billpay/transactionStatus/fetchInfo/xml',
        # Known alternate casing some deployments require.
        'xml_alt': 'billpay/transactionstatus/fetchinfo/xml',
    },
    'complaint_register': {
        'json': 'billpay/extComplaints/register/json',
        'xml': 'billpay/extComplaints/register/xml',
    },
    'complaint_track': {
        'json': 'billpay/extComplaints/track/json',
        'xml': 'billpay/extComplaints/track/xml',
    },
    'plan_pull': {
        'json': 'billpay/extPlanMDM/planMdmRequest/json',
        'xml': 'billpay/extPlanMDM/planMdmRequest/xml',
    },
    'deposit_enquiry': {
        'json': 'billpay/enquireDeposit/fetchDetails/json',
        'xml': 'billpay/enquireDeposit/fetchDetails/xml',
    },
}

# Transaction status: never use /xml here — many BillAvenue stacks return HTTP 404 on XML paths.
# Try lowercase JSON first, then camelCase JSON if the gateway only exposes one variant.
_TXN_STATUS_JSON_PATH_FALLBACKS = (
    'billpay/transactionstatus/fetchinfo/json',
    'billpay/transactionStatus/fetchInfo/json',
)


@dataclass
class BillAvenueResult:
    request_id: str
    response_code: str
    normalized: dict
    raw_response: dict


class BillAvenueClient:
    """Low-level BillAvenue API executor with encrypted envelope and normalized output."""

    def __init__(self, config: Optional[BillAvenueConfig] = None):
        self.config = config or BillAvenueConfig.objects.filter(is_active=True, enabled=True, is_deleted=False).first()
        if not self.config:
            raise BillAvenueClientError('No active BillAvenueConfig is configured.')
        raw_url = str(self.config.base_url or '').strip()
        if not raw_url:
            raise BillAvenueValidationError('BillAvenue Base URL is empty in active config.')
        parsed = urlparse(raw_url if '://' in raw_url else f'https://{raw_url}')
        if not parsed.scheme or not parsed.netloc:
            raise BillAvenueValidationError(
                f"Invalid BillAvenue Base URL '{raw_url}'. Use host URL like https://stgapi.billavenue.com"
            )
        # Normalize so endpoint joins remain stable.
        self.config.base_url = f"{parsed.scheme}://{parsed.netloc}"

    def _variant(self) -> str:
        fmt = str(getattr(self.config, 'api_format', 'json') or 'json').strip().lower()
        return 'xml' if fmt == 'xml' else 'json'

    def _safe_timeout_tuple(self, endpoint_name: str | None = None) -> tuple[int, int]:
        """
        Provider HTTP timeouts from admin config, with per-endpoint caps.
        bill_pay on UAT often exceeds 20s; gunicorn worker timeout must allow the read cap (see run_gunicorn.sh).
        """
        def _to_int(value, fallback: int) -> int:
            try:
                n = int(value)
            except Exception:
                n = fallback
            return n if n > 0 else fallback

        connect_cfg = _to_int(getattr(self.config, 'connect_timeout_seconds', 30), 30)
        read_cfg = _to_int(getattr(self.config, 'read_timeout_seconds', 60), 60)
        connect_cap = 15
        read_caps = {
            'bill_fetch': 35,
            'bill_validate': 35,
            'bill_pay': 60,
            'txn_status': 30,
            'plan_pull': 45,
        }
        default_read_cap = 35
        ep = str(endpoint_name or '').strip().lower()
        read_cap = read_caps.get(ep, default_read_cap)
        connect_timeout = min(max(connect_cfg, 2), connect_cap)
        read_timeout = min(max(read_cfg, 5), read_cap)
        return (connect_timeout, read_timeout)

    def _endpoint_for(self, endpoint_key: str) -> str:
        """Resolve HTTP path for BillAvenue.

        Complaint register/track always use the **/xml** paths with XML inside ``encRequest`` (BillAvenue
        reference). When api_format=xml we only build native XML plaintext for MDM (`biller_info`) and plan MDM
        (`plan_pull`). Other non-complaint calls still use JSON-shaped plaintext inside encRequest with **/json**
        URLs when api_format=xml (see branch below).
        """
        mapping = _ENDPOINTS_BY_KEY.get(endpoint_key) or {}
        # BillAvenue complaint APIs: official samples use /extComplaints/{register|track}/xml with XML
        # inside encRequest (query-string envelope). JSON + /json often yields 205 FAILURE on UAT.
        if endpoint_key in ('complaint_register', 'complaint_track'):
            return str(mapping.get('xml') or mapping.get('json') or '').strip()
        # Transaction status endpoint is consistently deployed on /json in BillAvenue stacks.
        # Avoid /xml entirely here; some environments return 404 on /xml and break end-user query screens.
        if endpoint_key == 'txn_status':
            return str(_TXN_STATUS_JSON_PATH_FALLBACKS[0] if _TXN_STATUS_JSON_PATH_FALLBACKS else mapping.get('json') or '').strip()
        v = self._variant()
        if v == 'xml' and endpoint_key not in ('biller_info', 'plan_pull', 'bill_fetch', 'bill_pay'):
            return str(mapping.get('json') or '').strip()
        return str(mapping.get(v) or mapping.get('json') or '').strip()

    def _inner_plaintext_for_post(self, endpoint_name: str, payload_obj: dict) -> str:
        """Encrypted inner body: JSON for /json URLs; XML for MDM, bill fetch/pay, plan MDM, and complaints."""
        if endpoint_name == 'complaint_register':
            return build_complaint_register_plain_xml(payload_obj or {})
        if endpoint_name == 'complaint_track':
            return build_complaint_track_plain_xml(payload_obj or {})
        if self._variant() == 'json':
            return json.dumps(payload_obj or {}, separators=(',', ':'))
        if endpoint_name == 'biller_info':
            return build_biller_info_plain_xml(payload_obj or {})
        if endpoint_name == 'bill_fetch':
            return build_bill_fetch_plain_xml(payload_obj or {})
        if endpoint_name == 'bill_pay':
            return build_bill_pay_plain_xml(payload_obj or {})
        if endpoint_name == 'plan_pull':
            return build_plan_pull_plain_xml(payload_obj or {})
        # Other endpoints use /json URLs when api_format=xml (see _endpoint_for); inner body is JSON.
        return json.dumps(payload_obj or {}, separators=(',', ':'))

    @staticmethod
    def _looks_like_hex_cipher(text: str) -> bool:
        s = str(text or '').strip()
        if not s or len(s) < 32 or (len(s) % 2) != 0:
            return False
        return all(ch in '0123456789abcdefABCDEF' for ch in s)

    def _decrypt_and_parse_best_effort(self, cipher_text: str) -> dict | None:
        raw = str(cipher_text or '').strip()
        if not raw:
            return None
        derivations = []
        configured = str(getattr(self.config, 'crypto_key_derivation', 'rawhex') or 'rawhex').strip().lower()
        derivations.append(configured)
        for alt in ('md5', 'rawhex'):
            if alt not in derivations:
                derivations.append(alt)
        for kd in derivations:
            try:
                plain = decrypt_payload_auto(
                    raw,
                    working_key=self.config.get_working_key(),
                    iv=self.config.get_iv(),
                    key_derivation=kd,
                )
                plain = normalize_decrypted_plaintext(plain)
                parsed = _retry_parse_if_only_raw(parse_payload_text(plain), plain)
                if isinstance(parsed, dict) and parsed and not (
                    len(parsed) == 1 and 'raw' in parsed and str(parsed.get('raw') or '').strip() == raw
                ):
                    return parsed
            except Exception:
                continue
        return None

    def _post(
        self,
        *,
        payload_obj: dict,
        endpoint_name: str,
        request_id: str | None = None,
        ver_override: str | None = None,
        key_derivation_override: str | None = None,
        enc_request_encoding_override: str | None = None,
        _enc_retry_attempted: bool = False,
        _force_json: bool = False,
        _json_fallback_attempted: bool = False,
    ) -> BillAvenueResult:
        if not self.config.enabled:
            raise BillAvenueClientError('BillAvenue integration is disabled by admin configuration.')

        working_key = str(self.config.get_working_key() or '').strip()
        if not working_key or len(working_key) < 16:
            env_label = normalize_billavenue_mode(getattr(self.config, 'mode', None)).upper()
            raise BillAvenueAuthError(
                f'BillAvenue {env_label} Working Key is not configured correctly. '
                'Open BBPS Console → BillAvenue Settings → Encrypted secrets, then retry.'
            )
        # IV: invalid/missing values fall back to BILLAVENUE_STANDARD_IV_HEX in crypto.py (PHP sample).

        working_payload = dict(payload_obj or {})
        plan_pull_raw_body = bool(working_payload.pop('_mpayhub_plan_pull_raw_body', False))

        use_json_body = bool(_force_json) or self._variant() == 'json'
        if use_json_body and endpoint_name not in ('complaint_register', 'complaint_track'):
            payload_text = json.dumps(working_payload or {}, separators=(',', ':'))
        else:
            payload_text = self._inner_plaintext_for_post(endpoint_name, working_payload)
        env = build_encrypted_envelope(
            payload_text=payload_text,
            access_code=self.config.access_code,
            institute_id=self.config.institute_id,
            ver=(ver_override or self.config.request_version),
            working_key=self.config.get_working_key(),
            iv=self.config.get_iv(),
            request_id=request_id,
            key_derivation=str(
                key_derivation_override
                or getattr(self.config, 'crypto_key_derivation', 'rawhex')
                or 'rawhex'
            ),
            enc_request_encoding=str(
                enc_request_encoding_override
                or getattr(self.config, 'enc_request_encoding', 'base64')
                or 'base64'
            ),
        )

        if _force_json and endpoint_name == 'plan_pull':
            mapping = _ENDPOINTS_BY_KEY.get(endpoint_name) or {}
            endpoint = str(mapping.get('json') or mapping.get('xml') or '').strip()
        else:
            endpoint = self._endpoint_for(endpoint_name)
        if not endpoint:
            raise BillAvenueValidationError(f"Unknown BillAvenue endpoint for '{endpoint_name}'")
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        started = timezone.now()
        request_meta = {
            'url': url,
            'transport': 'json-envelope',
            'variant': 'json' if use_json_body else self._variant(),
            'force_json': bool(_force_json),
            'crypto_key_derivation': str(
                key_derivation_override
                or getattr(self.config, 'crypto_key_derivation', '')
                or ''
            ),
            'enc_request_encoding': str(
                enc_request_encoding_override
                or getattr(self.config, 'enc_request_encoding', '')
                or ''
            ),
        }
        try:
            timeout = self._safe_timeout_tuple(endpoint_name)
            request_meta = {
                **request_meta,
                'timeout_connect_seconds': timeout[0],
                'timeout_read_seconds': timeout[1],
            }
            if endpoint_name == 'biller_info':
                # BillAvenue note: Biller Info expects encRequest in raw body.
                query = {
                    'accessCode': env['accessCode'],
                    'requestId': env['requestId'],
                    'ver': env['ver'],
                    'instituteId': env['instituteId'],
                }
                request_meta = {
                    **request_meta,
                    'url': url,
                    'transport': 'raw-encRequest-body',
                    'query': query,
                }
                resp = requests.post(
                    url,
                    params=query,
                    data=env['encRequest'],
                    headers={'Content-Type': 'text/plain; charset=utf-8'},
                    timeout=timeout,
                )
            elif endpoint_name == 'plan_pull':
                # Plan MDM: Postman uses form urlencoded; some stacks also accept raw body like biller_info.
                if plan_pull_raw_body:
                    query = {
                        'accessCode': env['accessCode'],
                        'requestId': env['requestId'],
                        'ver': env['ver'],
                        'instituteId': env['instituteId'],
                    }
                    request_meta = {
                        **request_meta,
                        'url': url,
                        'transport': 'raw-encRequest-body',
                        'query': query,
                    }
                    resp = requests.post(
                        url,
                        params=query,
                        data=env['encRequest'],
                        headers={'Content-Type': 'text/plain; charset=utf-8'},
                        timeout=timeout,
                    )
                else:
                    request_meta = {**request_meta, 'transport': 'form-post-params'}
                    resp = requests.post(url, data=env, timeout=timeout)
            elif endpoint_name in ('complaint_register', 'complaint_track'):
                # BillAvenue (2026): extComplaints expects accessCode, requestId, instituteId, ver, encRequest
                # as query parameters — not as x-www-form-urlencoded POST body.
                request_meta = {
                    **request_meta,
                    'url': url,
                    'transport': 'complaint-envelope-query-string',
                }
                resp = requests.post(url, params=env, timeout=timeout)
            else:
                # BillAvenue note: other APIs accept encRequest as POST parameter.
                base = self.config.base_url.rstrip('/')
                request_meta = {**request_meta, 'transport': 'form-post-params'}
                if (
                    endpoint_name == 'txn_status'
                    and bool(getattr(self.config, 'allow_txn_status_path_fallback', True))
                ):
                    # Retry alternate JSON paths on 404 (XML paths and wrong casing both surface as 404).
                    primary_path = str(endpoint or '').lstrip('/')
                    ordered = []
                    seen_paths = set()
                    for p in (primary_path,) + _TXN_STATUS_JSON_PATH_FALLBACKS:
                        p_norm = str(p or '').lstrip('/')
                        if p_norm and p_norm not in seen_paths:
                            seen_paths.add(p_norm)
                            ordered.append(p_norm)
                    attempts = []
                    resp = None
                    for path in ordered:
                        try_url = f"{base}/{path}"
                        attempts.append(try_url)
                        resp = requests.post(try_url, data=env, timeout=timeout)
                        if resp.status_code != 404:
                            break
                    request_meta['url'] = attempts[-1] if attempts else url
                    request_meta['txn_status_url_attempts'] = attempts
                else:
                    request_meta = {**request_meta, 'url': url}
                    resp = requests.post(url, data=env, timeout=timeout)
            resp.raise_for_status()
            data = resp.json() if 'application/json' in (resp.headers.get('Content-Type') or '').lower() else {'raw': resp.text}
        except requests.exceptions.Timeout as exc:
            err = f"TIMEOUT endpoint={endpoint_name} connect={timeout[0]}s read={timeout[1]}s: {exc}"
            self._audit(endpoint_name, env.get('requestId', ''), '', False, started, request_meta, {}, err)
            te = BillAvenueTransportError(err)
            _attach_billavenue_request_id(te, env.get('requestId', ''))
            raise te from exc
        except Exception as exc:
            self._audit(endpoint_name, env.get('requestId', ''), '', False, started, request_meta, {}, str(exc))
            te = BillAvenueTransportError(str(exc))
            _attach_billavenue_request_id(te, env.get('requestId', ''))
            raise te from exc

        enc_resp = _extract_enc_response_field(data)
        decrypted_plain = ''
        if enc_resp:
            plain = decrypt_payload_auto(
                enc_resp,
                working_key=self.config.get_working_key(),
                iv=self.config.get_iv(),
                key_derivation=str(getattr(self.config, 'crypto_key_derivation', 'rawhex') or 'rawhex'),
            )
            plain = normalize_decrypted_plaintext(plain)
            decrypted_plain = str(plain or '')
            normalized = _retry_parse_if_only_raw(parse_payload_text(plain), plain)
            # If primary decrypt produced only raw text, retry with alternate key derivations on encResponse.
            if isinstance(normalized, dict) and set(normalized.keys()) == {'raw'}:
                rescued = self._decrypt_and_parse_best_effort(enc_resp)
                if rescued:
                    normalized = rescued
        else:
            # Some XML endpoints return ciphertext as whole-body, not as encResponse field.
            # Others (errors) return plaintext XML/JSON — decrypt fails; parse as plaintext.
            raw_text = ''
            if isinstance(data, dict):
                raw_text = str(data.get('raw') or data.get('encResponse') or '')
            if not raw_text and isinstance(data, dict) and data:
                # Unexpected JSON shape without encResponse — keep as-is for code extraction.
                normalized = data
            elif raw_text:
                try:
                    plain = decrypt_payload_auto(
                        raw_text,
                        working_key=self.config.get_working_key(),
                        iv=self.config.get_iv(),
                        key_derivation=str(getattr(self.config, 'crypto_key_derivation', 'rawhex') or 'rawhex'),
                    )
                    plain = normalize_decrypted_plaintext(plain)
                    decrypted_plain = str(plain or '')
                    normalized = _retry_parse_if_only_raw(parse_payload_text(plain), plain)
                except Exception:
                    normalized = _retry_parse_if_only_raw(parse_payload_text(raw_text), raw_text)
                    if isinstance(normalized, dict) and set(normalized.keys()) == {'raw'}:
                        # Keep original envelope for diagnostics if plaintext parse also failed.
                        normalized = data if isinstance(data, dict) else {'raw': raw_text}
            else:
                normalized = data if isinstance(data, dict) else {'raw': data}

        # Last-pass rescue: some MDM deployments return ciphertext as raw body and may require
        # alternate key-derivation interpretation despite configured mode.
        raw_text = ''
        if isinstance(normalized, dict):
            raw_text = str(normalized.get('raw') or '').strip()
        if self._looks_like_hex_cipher(raw_text):
            rescued = self._decrypt_and_parse_best_effort(raw_text)
            if rescued:
                normalized = rescued
        elif raw_text and isinstance(normalized, dict) and set(normalized.keys()) == {'raw'}:
            # Plaintext XML/JSON stuck in raw (common for gateway error bodies).
            rescued_plain = _retry_parse_if_only_raw(normalized, raw_text)
            if isinstance(rescued_plain, dict) and rescued_plain and set(rescued_plain.keys()) != {'raw'}:
                normalized = rescued_plain

        raw_text = ''
        if isinstance(normalized, dict):
            raw_text = str(normalized.get('raw') or '')
        if raw_text:
            low = raw_text.lower()
            if 'unauthorized access detected' in low or 'access denied' in low:
                code = 'PP001'
                self._audit(endpoint_name, env.get('requestId', ''), code, False, started, request_meta, {'normalized': normalized}, 'Unauthorized access from BillAvenue module')
                ae = BillAvenueAuthError(
                    f"BillAvenue access denied for endpoint '{endpoint_name}' (requestId={env.get('requestId','')}). "
                    'Verify Access Code/Institute ID/Agent privileges and endpoint entitlement.'
                )
                _attach_billavenue_request_id(ae, env.get('requestId', ''))
                raise ae

        # MDM XML can occasionally be mis-parsed as a bare JSON list (e.g. ``[12]`` fragment).
        # Also accept a list of biller dicts as a successful MDM shape.
        if isinstance(normalized, list):
            if normalized and all(isinstance(x, dict) for x in normalized):
                normalized = {
                    'billerInfoResponse': {
                        'responseCode': '000',
                        'biller': normalized,
                    }
                }
            else:
                normalized = {
                    'raw': json.dumps(normalized, ensure_ascii=False),
                    '_mpayhub_parse_note': 'list_payload_without_biller_dicts',
                }

        code = extract_complaint_api_outcome_code(normalized) if endpoint_name in ('complaint_register', 'complaint_track') else extract_response_code(normalized)
        # Some providers return decrypted JSON/XML text as a string under raw; recover code from it.
        if not code and isinstance(normalized, dict):
            raw = str(normalized.get('raw') or '').strip()
            if raw:
                rescued = _retry_parse_if_only_raw({'raw': raw}, raw)
                if isinstance(rescued, dict) and set(rescued.keys()) != {'raw'}:
                    normalized = rescued
                    if endpoint_name in ('complaint_register', 'complaint_track'):
                        code = extract_complaint_api_outcome_code(normalized)
                    else:
                        code = extract_response_code(normalized)
            if not code and (raw.startswith('{') or raw.startswith('[')):
                try:
                    parsed_raw = json.loads(raw)
                    if isinstance(parsed_raw, dict):
                        if endpoint_name in ('complaint_register', 'complaint_track'):
                            recovered = extract_complaint_api_outcome_code(parsed_raw)
                        else:
                            recovered = extract_response_code(parsed_raw)
                        if recovered:
                            normalized = parsed_raw
                            code = recovered
                except Exception:
                    pass

        # UAT safety net: retry with alternate crypto if upstream says Invalid ENC.
        if (
            endpoint_name in ('bill_pay', 'plan_pull', 'bill_fetch', 'bill_validate')
            and not _enc_retry_attempted
            and _has_invalid_enc_request(normalized if isinstance(normalized, dict) else {})
        ):
            current_kd = str(
                key_derivation_override
                or getattr(self.config, 'crypto_key_derivation', 'rawhex')
                or 'rawhex'
            ).strip().lower()
            current_enc = str(
                enc_request_encoding_override
                or getattr(self.config, 'enc_request_encoding', 'base64')
                or 'base64'
            ).strip().lower()
            candidates = [
                ('md5', 'hex'),
                ('rawhex', 'hex'),
                ('md5', 'base64'),
                ('rawhex', 'base64'),
            ]
            last_exc = None
            for kd, enc in candidates:
                if kd == current_kd and enc == current_enc:
                    continue
                logger.warning(
                    "BillAvenue %s returned Invalid ENC; retrying with %s+%s (requestId=%s).",
                    endpoint_name,
                    kd,
                    enc,
                    env.get('requestId', ''),
                )
                try:
                    return self._post(
                        payload_obj=payload_obj,
                        endpoint_name=endpoint_name,
                        request_id=request_id,
                        ver_override=ver_override,
                        key_derivation_override=kd,
                        enc_request_encoding_override=enc,
                        _enc_retry_attempted=True,
                        _force_json=_force_json,
                        # Prevent each crypto retry from also spawning JSON fallbacks.
                        _json_fallback_attempted=True,
                    )
                except BillAvenueClientError as exc:
                    last_exc = exc
                    continue
            if last_exc and endpoint_name != 'plan_pull':
                raise last_exc
            # plan_pull: fall through to JSON path fallback below when still failing.

        # Plan MDM Postman samples use /json; if XML+ENC still fails, retry once as JSON.
        if (
            endpoint_name == 'plan_pull'
            and not _json_fallback_attempted
            and not _force_json
            and self._variant() == 'xml'
            and _has_invalid_enc_request(normalized if isinstance(normalized, dict) else {})
        ):
            logger.warning(
                "BillAvenue plan_pull still Invalid ENC on XML; retrying JSON path (requestId=%s).",
                env.get('requestId', ''),
            )
            return self._post(
                payload_obj=payload_obj,
                endpoint_name=endpoint_name,
                request_id=request_id,
                ver_override=ver_override,
                key_derivation_override=key_derivation_override,
                enc_request_encoding_override=enc_request_encoding_override,
                _enc_retry_attempted=False,
                _force_json=True,
                _json_fallback_attempted=True,
            )

        response_meta = {'normalized': normalized}
        if endpoint_name in ('complaint_register', 'complaint_track'):
            err = _extract_error_block(normalized if isinstance(normalized, dict) else {})
            if err:
                response_meta['provider_error'] = err

        # Do not treat a missing code as success; unparseable bodies often yield '' and would mask failures.
        ok = str(code or '').strip() in ('000', '0')
        self._audit(endpoint_name, env.get('requestId', ''), code, ok, started, request_meta, response_meta, '')
        if not ok:
            c = str(code or '').strip()
            if not c:
                keys = list(normalized.keys())[:12] if isinstance(normalized, dict) else []
                raw_preview = ''
                if isinstance(normalized, dict):
                    raw_preview = str(normalized.get('raw') or '')[:180].replace('\n', ' ')
                ce = BillAvenueClientError(
                    f"BillAvenue API failed ({endpoint_name}): missing responseCode in parsed gateway payload "
                    f"(top-level keys: {keys}; raw-preview: {raw_preview}). "
                    'Check UAT credentials, endpoint version, and BillAvenue response format.'
                )
                _attach_billavenue_request_id(ce, env.get('requestId', ''))
                raise ce
            exc_cls = exception_for_code(code)
            if endpoint_name in ('complaint_register', 'complaint_track'):
                provider_err = _extract_complaint_response_reason(
                    normalized if isinstance(normalized, dict) else {}
                )
                if not provider_err and isinstance(normalized, dict):
                    blk = _extract_error_block(normalized)
                    provider_err = str(blk.get('errorMessage') or '').strip()
                if not provider_err:
                    provider_err = _error_message_from_normalized(normalized if isinstance(normalized, dict) else {})
            else:
                provider_err = _error_message_from_normalized(normalized if isinstance(normalized, dict) else {})
            if provider_err and len(provider_err) > 1800:
                provider_err = provider_err[:1800] + '…'
            suffix = f' ({provider_err})' if provider_err else ''
            blk = _extract_error_block_deep(normalized if isinstance(normalized, dict) else {})
            provider_code = str(blk.get('errorCode') or '').strip()
            if not provider_code and provider_err:
                # e.g. "E135 — Mandatory ..."
                provider_code = provider_err.split('—', 1)[0].strip() if '—' in provider_err else ''
            pe = exc_cls(
                f'BillAvenue API failed ({endpoint_name}) code={c}{suffix}',
                provider_code=provider_code,
            )
            _attach_billavenue_request_id(pe, env.get('requestId', ''))
            raise pe
        if endpoint_name == 'bill_fetch' and decrypted_plain.strip() and isinstance(normalized, dict):
            frag = extract_element_outer_xml_from_plaintext(decrypted_plain, 'billerResponse')
            if frag:
                normalized = {**normalized, '__mpayhub_biller_response_xml': frag}
            # Root-level additionalInfo only (never the nested copy inside billerResponse) — E212.
            addl_frag = extract_element_outer_xml_from_plaintext(
                decrypted_plain,
                'additionalInfo',
                not_under_local_names=frozenset({'billerresponse'}),
            )
            if addl_frag:
                normalized = {**normalized, '__mpayhub_additional_info_xml': addl_frag}
        return BillAvenueResult(request_id=env['requestId'], response_code=code, normalized=normalized, raw_response=data)

    def _audit(self, endpoint_name, request_id, response_code, success, started_at, request_meta, response_meta, error_message):
        try:
            latency = int((timezone.now() - started_at).total_seconds() * 1000)
            BbpsApiAuditLog.objects.create(
                endpoint_name=endpoint_name,
                request_id=request_id,
                status_code=response_code,
                success=success,
                latency_ms=max(0, latency),
                request_meta=request_meta if isinstance(request_meta, dict) else {'raw': str(request_meta)},
                response_meta=response_meta if isinstance(response_meta, dict) else {'raw': str(response_meta)},
                error_message=(error_message or '')[:2000],
            )
        except Exception:
            logger.exception('BillAvenue audit log create failed')

    def biller_info(self, payload: dict, *, request_id: str | None = None) -> BillAvenueResult:
        return self._post(payload_obj=payload, endpoint_name='biller_info', request_id=request_id)

    def bill_fetch(self, payload: dict, *, request_id: str | None = None) -> BillAvenueResult:
        return self._post(payload_obj=payload, endpoint_name='bill_fetch', request_id=request_id)

    def bill_validate(self, payload: dict, *, request_id: str | None = None) -> BillAvenueResult:
        return self._post(payload_obj=payload, endpoint_name='bill_validate', request_id=request_id)

    def bill_pay(self, payload: dict, *, request_id: str | None = None) -> BillAvenueResult:
        return self._post(payload_obj=payload, endpoint_name='bill_pay', request_id=request_id)

    def transaction_status(self, payload: dict, *, request_id: str | None = None) -> BillAvenueResult:
        return self._post(payload_obj=payload, endpoint_name='txn_status', request_id=request_id)

    def complaint_register(self, payload: dict, *, request_id: str | None = None) -> BillAvenueResult:
        return self._post(
            payload_obj=payload,
            endpoint_name='complaint_register',
            request_id=request_id,
            ver_override='2.0',
        )

    def complaint_track(self, payload: dict, *, request_id: str | None = None) -> BillAvenueResult:
        return self._post(
            payload_obj=payload,
            endpoint_name='complaint_track',
            request_id=request_id,
            ver_override='2.0',
        )

    def plan_pull(self, payload: dict, *, request_id: str | None = None) -> BillAvenueResult:
        """
        Plan MDM pull. Prefer JSON (Postman sample) with billerId only; fall back to XML/raw body.
        """
        base = dict(payload or {})
        # Internal transport hint must not go into encrypted plaintext.
        base.pop('_mpayhub_plan_pull_raw_body', None)

        attempts = []
        # 1) JSON + form (Postman)
        attempts.append({'force_json': True, 'raw_body': False, 'drop_agent': True})
        # 2) JSON + form with agentId kept
        attempts.append({'force_json': True, 'raw_body': False, 'drop_agent': False})
        # 3) Config variant (often XML) + form
        attempts.append({'force_json': False, 'raw_body': False, 'drop_agent': True})
        # 4) JSON + raw body (like biller_info)
        attempts.append({'force_json': True, 'raw_body': True, 'drop_agent': True})

        last_exc = None
        for idx, attempt in enumerate(attempts):
            req = dict(base)
            if attempt['drop_agent']:
                req.pop('agentId', None)
            if attempt['raw_body']:
                req['_mpayhub_plan_pull_raw_body'] = True
            try:
                return self._post(
                    payload_obj=req,
                    endpoint_name='plan_pull',
                    request_id=request_id,
                    _force_json=bool(attempt['force_json']),
                    _enc_retry_attempted=False,
                    _json_fallback_attempted=True,  # avoid nested JSON fallback; we drive attempts here
                )
            except BillAvenueClientError as exc:
                last_exc = exc
                low = str(exc or '').lower()
                if 'pp002' not in low and 'invalid enc' not in low and 'de001' not in low:
                    raise
                logger.warning(
                    "BillAvenue plan_pull attempt %s failed (%s); trying next strategy.",
                    idx + 1,
                    str(exc)[:160],
                )
                continue
        if last_exc:
            raise last_exc
        raise BillAvenueClientError('BillAvenue plan_pull failed with no attempts executed.')

    def deposit_enquiry(self, payload: dict, *, request_id: str | None = None) -> BillAvenueResult:
        return self._post(payload_obj=payload, endpoint_name='deposit_enquiry', request_id=request_id)
