import json
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import requests
from django.utils import timezone

from apps.integrations.billavenue.crypto import decrypt_payload_auto
from apps.integrations.billavenue.envelope import build_encrypted_envelope
from apps.integrations.billavenue.errors import (
    BillAvenueAuthError,
    BillAvenueClientError,
    BillAvenueTransportError,
    BillAvenueValidationError,
    exception_for_code,
)
from apps.integrations.billavenue.parsers import extract_response_code, parse_payload_text
from apps.integrations.models import BillAvenueConfig
from apps.bbps.models import BbpsApiAuditLog

logger = logging.getLogger(__name__)

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

    def _endpoint_for(self, endpoint_key: str) -> str:
        v = self._variant()
        mapping = _ENDPOINTS_BY_KEY.get(endpoint_key) or {}
        return str(mapping.get(v) or mapping.get('json') or '').strip()

    def _post(
        self,
        *,
        payload_obj: dict,
        endpoint_name: str,
        request_id: str | None = None,
        ver_override: str | None = None,
    ) -> BillAvenueResult:
        if not self.config.enabled:
            raise BillAvenueClientError('BillAvenue integration is disabled by admin configuration.')

        payload_text = json.dumps(payload_obj, separators=(',', ':'))
        env = build_encrypted_envelope(
            payload_text=payload_text,
            access_code=self.config.access_code,
            institute_id=self.config.institute_id,
            ver=(ver_override or self.config.request_version),
            working_key=self.config.get_working_key(),
            iv=self.config.get_iv(),
            request_id=request_id,
            key_derivation=str(getattr(self.config, 'crypto_key_derivation', 'rawhex') or 'rawhex'),
            enc_request_encoding=str(getattr(self.config, 'enc_request_encoding', 'base64') or 'base64'),
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
            'crypto_key_derivation': str(getattr(self.config, 'crypto_key_derivation', '') or ''),
            'enc_request_encoding': str(getattr(self.config, 'enc_request_encoding', '') or ''),
        }
        try:
            timeout = (self.config.connect_timeout_seconds, self.config.read_timeout_seconds)
            if endpoint_name == 'biller_info':
                # BillAvenue note: Biller Info expects encRequest in raw body.
                query = {
                    'accessCode': env['accessCode'],
                    'requestId': env['requestId'],
                    'ver': env['ver'],
                    'instituteId': env['instituteId'],
                }
                request_meta = {'url': url, 'transport': 'raw-encRequest-body', 'query': query}
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
        except Exception as exc:
            self._audit(endpoint_name, env.get('requestId', ''), '', False, started, request_meta, {}, str(exc))
            raise BillAvenueTransportError(str(exc)) from exc

        enc_resp = str(data.get('encResponse') or data.get('encresponse') or '')
        if enc_resp:
            plain = decrypt_payload_auto(
                enc_resp,
                working_key=self.config.get_working_key(),
                iv=self.config.get_iv(),
                key_derivation=str(getattr(self.config, 'crypto_key_derivation', 'rawhex') or 'rawhex'),
            )
            normalized = parse_payload_text(plain)
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
                    normalized = parse_payload_text(plain)
                except Exception:
                    normalized = data if isinstance(data, dict) else {'raw': data}
            else:
                normalized = data if isinstance(data, dict) else {'raw': data}

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
        ok = code in ('000', '0', '')
        self._audit(endpoint_name, env.get('requestId', ''), code, ok, started, request_meta, {'normalized': normalized}, '')
        if not ok:
            exc_cls = exception_for_code(code)
            raise exc_cls(f'BillAvenue API failed ({endpoint_name}) code={code}')
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
