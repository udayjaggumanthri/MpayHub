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
    build_plan_pull_plain_xml,
)
from apps.integrations.billavenue.errors import (
    BillAvenueAuthError,
    BillAvenueClientError,
    BillAvenueTransportError,
    BillAvenueValidationError,
    exception_for_code,
)
from apps.integrations.billavenue.parsers import extract_response_code, normalize_decrypted_plaintext, parse_payload_text
from apps.integrations.models import BillAvenueConfig
from apps.bbps.models import BbpsApiAuditLog

logger = logging.getLogger(__name__)


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
    """If parse_payload_text fell back to {'raw': ...}, try JSON-in-string and second parse pass."""
    if not isinstance(normalized, dict) or set(normalized.keys()) != {'raw'}:
        return normalized
    inner = str(normalized.get('raw') or '').strip()
    if inner.startswith('"'):
        try:
            unwrapped = json.loads(inner)
            if isinstance(unwrapped, str):
                inner = unwrapped.strip()
            elif isinstance(unwrapped, dict):
                return unwrapped
        except Exception:
            pass
    if inner and inner != plain:
        retry = parse_payload_text(inner)
        if isinstance(retry, dict) and set(retry.keys()) != {'raw'}:
            return retry
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


def _has_invalid_enc_request(normalized: dict) -> bool:
    text = _normalized_text(normalized).lower()
    return 'de001' in text or 'invalid enc request' in text


def _error_message_from_normalized(normalized: dict) -> str:
    """Extract provider error text from normalized payload for operator-facing diagnostics."""
    text = _normalized_text(normalized)
    if not text:
        return ''
    low = text.lower()
    if 'invalid enc request' in low:
        return 'Invalid ENC request'
    if 'access denied' in low or 'unauthorized access detected' in low:
        return 'Access denied'
    if 'errorcode' in low or 'errormessage' in low:
        return text[:220]
    return ''


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
    if not code and not message:
        return {}
    return {'errorCode': code, 'errorMessage': message}


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

    def _safe_timeout_tuple(self) -> tuple[int, int]:
        """
        Keep provider timeouts bounded so upstream slowness does not exceed worker budget.
        Defaults still come from admin config but are clamped to safe limits.
        """
        def _to_int(value, fallback: int) -> int:
            try:
                n = int(value)
            except Exception:
                n = fallback
            return n if n > 0 else fallback

        connect_cfg = _to_int(getattr(self.config, 'connect_timeout_seconds', 5), 5)
        read_cfg = _to_int(getattr(self.config, 'read_timeout_seconds', 20), 20)
        connect_timeout = min(max(connect_cfg, 2), 10)
        # Keep bounded so sync workers can return graceful timeout responses (avoid worker aborts).
        read_timeout = min(max(read_cfg, 5), 20)
        return (connect_timeout, read_timeout)

    def _endpoint_for(self, endpoint_key: str) -> str:
        """Resolve HTTP path for BillAvenue.

        When api_format=xml we only build native XML plaintext for MDM (`biller_info`) and plan MDM
        (`plan_pull`). All other calls still use JSON-shaped plaintext inside encRequest — those must
        hit the **/json** URLs or BillAvenue commonly returns responseCode 001 on the /xml path.
        """
        mapping = _ENDPOINTS_BY_KEY.get(endpoint_key) or {}
        # Transaction status endpoint is consistently deployed on /json in BillAvenue stacks.
        # Avoid /xml entirely here; some environments return 404 on /xml and break end-user query screens.
        if endpoint_key == 'txn_status':
            return str(mapping.get('json') or '').strip()
        v = self._variant()
        if v == 'xml' and endpoint_key not in ('biller_info', 'plan_pull', 'bill_fetch', 'bill_pay'):
            return str(mapping.get('json') or '').strip()
        return str(mapping.get(v) or mapping.get('json') or '').strip()

    def _inner_plaintext_for_post(self, endpoint_name: str, payload_obj: dict) -> str:
        """Encrypted inner body: JSON for /json URLs; XML variant uses real XML for MDM/plan MDM, JSON fallback elsewhere."""
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
    ) -> BillAvenueResult:
        if not self.config.enabled:
            raise BillAvenueClientError('BillAvenue integration is disabled by admin configuration.')

        payload_text = self._inner_plaintext_for_post(endpoint_name, payload_obj)
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

        endpoint = self._endpoint_for(endpoint_name)
        if not endpoint:
            raise BillAvenueValidationError(f"Unknown BillAvenue endpoint for '{endpoint_name}'")
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        started = timezone.now()
        request_meta = {
            'url': url,
            'transport': 'json-envelope',
            'variant': self._variant(),
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
            timeout = self._safe_timeout_tuple()
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
            else:
                # BillAvenue note: other APIs accept encRequest as POST parameter.
                request_meta = {**request_meta, 'url': url, 'transport': 'form-post-params'}
                resp = requests.post(
                    url,
                    data=env,
                    timeout=timeout,
                )
                # Safe fallback: txn status casing mismatch can return HTML 404 on some deployments.
                if (
                    endpoint_name == 'txn_status'
                    and bool(getattr(self.config, 'allow_variant_fallback', True))
                    and bool(getattr(self.config, 'allow_txn_status_path_fallback', True))
                    and resp.status_code == 404
                    and 'text/html' in (resp.headers.get('Content-Type') or '').lower()
                ):
                    alt = _ENDPOINTS_BY_KEY.get('txn_status', {}).get('xml_alt') if self._variant() == 'xml' else None
                    if alt:
                        alt_url = f"{self.config.base_url.rstrip('/')}/{alt.lstrip('/')}"
                        request_meta = {**request_meta, 'txn_status_fallback_url': alt_url}
                        resp = requests.post(
                            alt_url,
                            data=env,
                            timeout=timeout,
                        )
            resp.raise_for_status()
            data = resp.json() if 'application/json' in (resp.headers.get('Content-Type') or '').lower() else {'raw': resp.text}
        except requests.exceptions.Timeout as exc:
            err = f"TIMEOUT endpoint={endpoint_name} connect={timeout[0]}s read={timeout[1]}s: {exc}"
            self._audit(endpoint_name, env.get('requestId', ''), '', False, started, request_meta, {}, err)
            raise BillAvenueTransportError(err) from exc
        except Exception as exc:
            self._audit(endpoint_name, env.get('requestId', ''), '', False, started, request_meta, {}, str(exc))
            raise BillAvenueTransportError(str(exc)) from exc

        enc_resp = _extract_enc_response_field(data)
        if enc_resp:
            plain = decrypt_payload_auto(
                enc_resp,
                working_key=self.config.get_working_key(),
                iv=self.config.get_iv(),
                key_derivation=str(getattr(self.config, 'crypto_key_derivation', 'rawhex') or 'rawhex'),
            )
            plain = normalize_decrypted_plaintext(plain)
            normalized = _retry_parse_if_only_raw(parse_payload_text(plain), plain)
            # If primary decrypt produced only raw text, retry with alternate key derivations on encResponse.
            if isinstance(normalized, dict) and set(normalized.keys()) == {'raw'}:
                rescued = self._decrypt_and_parse_best_effort(enc_resp)
                if rescued:
                    normalized = rescued
        else:
            # Some XML endpoints return ciphertext as whole-body, not as encResponse field.
            raw_text = ''
            if isinstance(data, dict):
                raw_text = str(data.get('raw') or '')
            if raw_text:
                try:
                    plain = decrypt_payload_auto(
                        raw_text,
                        working_key=self.config.get_working_key(),
                        iv=self.config.get_iv(),
                        key_derivation=str(getattr(self.config, 'crypto_key_derivation', 'rawhex') or 'rawhex'),
                    )
                    plain = normalize_decrypted_plaintext(plain)
                    normalized = _retry_parse_if_only_raw(parse_payload_text(plain), plain)
                except Exception:
                    normalized = data if isinstance(data, dict) else {'raw': data}
            else:
                normalized = data if isinstance(data, dict) else {'raw': data}

        # Last-pass rescue: some MDM deployments return ciphertext as raw body and may require
        # alternate key-derivation interpretation despite configured mode.
        raw_text = ''
        if isinstance(normalized, dict):
            raw_text = str(normalized.get('raw') or '')
        if self._looks_like_hex_cipher(raw_text):
            rescued = self._decrypt_and_parse_best_effort(raw_text)
            if rescued:
                normalized = rescued

        raw_text = ''
        if isinstance(normalized, dict):
            raw_text = str(normalized.get('raw') or '')
        if raw_text:
            low = raw_text.lower()
            if 'unauthorized access detected' in low or 'access denied' in low:
                code = 'PP001'
                self._audit(endpoint_name, env.get('requestId', ''), code, False, started, request_meta, {'normalized': normalized}, 'Unauthorized access from BillAvenue module')
                raise BillAvenueAuthError(
                    f"BillAvenue access denied for endpoint '{endpoint_name}' (requestId={env.get('requestId','')}). "
                    'Verify Access Code/Institute ID/Agent privileges and endpoint entitlement.'
                )

        code = extract_response_code(normalized)
        # Some providers return decrypted JSON text as a string; recover code from it.
        if not code and isinstance(normalized, dict):
            raw = str(normalized.get('raw') or '').strip()
            if raw.startswith('{') or raw.startswith('['):
                try:
                    parsed_raw = json.loads(raw)
                    if isinstance(parsed_raw, dict):
                        recovered = extract_response_code(parsed_raw)
                        if recovered:
                            normalized = parsed_raw
                            code = recovered
                except Exception:
                    pass

        # UAT safety net: retry bill-pay once with md5+hex if upstream says Invalid ENC request.
        if (
            endpoint_name == 'bill_pay'
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
                    "BillAvenue bill_pay returned DE001; retrying with %s+%s (requestId=%s).",
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
                    )
                except BillAvenueClientError as exc:
                    last_exc = exc
                    continue
            if last_exc:
                raise last_exc

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
                raise BillAvenueClientError(
                    f"BillAvenue API failed ({endpoint_name}): missing responseCode in parsed gateway payload "
                    f"(top-level keys: {keys}; raw-preview: {raw_preview}). "
                    'Check UAT credentials, endpoint version, and BillAvenue response format.'
                )
            exc_cls = exception_for_code(code)
            provider_err = _error_message_from_normalized(normalized if isinstance(normalized, dict) else {})
            suffix = f' ({provider_err})' if provider_err else ''
            raise exc_cls(f'BillAvenue API failed ({endpoint_name}) code={c}{suffix}')
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
        return self._post(payload_obj=payload, endpoint_name='plan_pull', request_id=request_id)

    def deposit_enquiry(self, payload: dict, *, request_id: str | None = None) -> BillAvenueResult:
        return self._post(payload_obj=payload, endpoint_name='deposit_enquiry', request_id=request_id)
