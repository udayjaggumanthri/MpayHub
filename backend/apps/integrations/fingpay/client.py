"""
Thin HTTP client for Fingpay AEPS APIs.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from apps.integrations.fingpay.crypto import (
    build_encrypted_request,
    build_recon_hash,
    md5_hex,
    scrub_sensitive,
)

logger = logging.getLogger(__name__)


SERVER_EGRESS_IP = '57.131.39.21'


class FingpayClientError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any = None,
        exchange: dict | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload
        self.exchange = exchange or {}


class FingpayClient:
    ONBOARDING_CREATE_PATHS = {
        'java': '/api/onboarding/merchant/creation/v2',
        'php': '/api/onboarding/merchant/php/creation/v2',
    }

    def __init__(
        self,
        *,
        super_merchant_id: str,
        super_merchant_login_id: str,
        password_plain: str,
        secret_key: str,
        rsa_public_key_pem: str,
        onboarding_base_url: str,
        ekyc_base_url: str,
        aeps_base_url: str,
        recon_base_url: str = '',
        timeout: int = 180,
        onboarding_api_style: str = 'java',
        environment: str = '',
    ):
        self.super_merchant_id = str(super_merchant_id)
        self.super_merchant_login_id = super_merchant_login_id
        self.password_md5 = md5_hex(password_plain) if password_plain else ''
        self.secret_key = secret_key
        self.rsa_public_key_pem = rsa_public_key_pem
        self.onboarding_base_url = onboarding_base_url.rstrip('/')
        self.ekyc_base_url = ekyc_base_url.rstrip('/')
        self.aeps_base_url = aeps_base_url.rstrip('/')
        self.recon_base_url = (recon_base_url or '').rstrip('/')
        self.timeout = max(30, int(timeout or 180))
        style = (onboarding_api_style or 'java').lower()
        self.onboarding_api_style = style if style in self.ONBOARDING_CREATE_PATHS else 'java'
        self.environment = (environment or '').lower()

    def onboarding_create_url(self) -> str:
        path = self.ONBOARDING_CREATE_PATHS[self.onboarding_api_style]
        return f'{self.onboarding_base_url}{path}'

    def onboarding_aes_mode(self) -> str:
        return 'cbc' if self.onboarding_api_style == 'php' else 'ecb'

    @staticmethod
    def _header_summary(headers: dict) -> dict:
        out = {}
        for k, v in (headers or {}).items():
            key = str(k)
            val = str(v or '')
            if key.lower() in ('hash', 'eskey', 'authorization'):
                out[key] = f'<len={len(val)}>'
            else:
                out[key] = val
        return out

    def _build_exchange(
        self,
        *,
        method: str,
        url: str,
        request_headers: dict,
        plain_payload: dict | None,
        encrypted_body_bytes: int | None,
        mode: str,
        resp: Any = None,
        transport_error: str | None = None,
        latency_ms: int | None = None,
        encrypted_body_preview: str = '',
    ) -> dict:
        response_block: dict[str, Any] = {
            'transport_error': transport_error,
            'latency_ms': latency_ms,
        }
        if resp is not None:
            try:
                body = resp.json()
            except Exception:
                body = {'raw_html_or_text': (resp.text or '')[:4000]}
            response_block.update(
                {
                    'http_status': resp.status_code,
                    'headers': {
                        'server': resp.headers.get('server'),
                        'content-type': resp.headers.get('content-type'),
                        'content-length': resp.headers.get('content-length'),
                        'date': resp.headers.get('date'),
                    },
                    'body': scrub_sensitive(body) if isinstance(body, (dict, list)) else body,
                }
            )
        diagnosis = ''
        http_status = response_block.get('http_status')
        if http_status == 403 and str(response_block.get('headers', {}).get('server') or '').lower().startswith(
            'awselb'
        ):
            diagnosis = (
                f'AWS ELB returned HTTP 403 before the Fingpay app. '
                f'Source IP {SERVER_EGRESS_IP} is still blocked on fingpayap.tapits.in. '
                'Whitelist is NOT effective yet for this host/IP.'
            )
        elif transport_error:
            diagnosis = f'Transport failure: {transport_error}'
        elif http_status and int(http_status) >= 400:
            diagnosis = f'HTTP {http_status} from Fingpay edge/app.'
        else:
            diagnosis = 'Reached Fingpay application layer (inspect statusCode/message).'

        plain = scrub_sensitive(plain_payload or {}, for_tapits=True)
        resp_body = response_block.get('body')
        if isinstance(resp_body, (dict, list)):
            resp_body = scrub_sensitive(resp_body, for_tapits=True)
        # Doc "Sample Headers and Body" shows full trnTimestamp/hash/eskey values —
        # neither is a secret (hash = SHA256 of payload; eskey is RSA-encrypted,
        # only Fingpay's private key can open it), so share the real values.
        share_headers = {str(k): str(v or '') for k, v in (request_headers or {}).items()}
        style = getattr(self, 'onboarding_api_style', '') or (
            'php' if 'cbc' in (mode or '') else 'java'
        )
        share = {
            'endpoint': f'{method} {url}',
            'doc': (
                f'Fingpay Services API Doc 270426 — Merchant Onboarding '
                f'{"PHP" if style == "php" else "Java/.NET"} path. '
                f'Active admin style={style}; '
                f'encryption={"AES-128-CBC + text/xml (phpsamplecode.txt)" if style == "php" else "AES-128-ECB (AEPS_RSA.net sample)"}.'
            ),
            'environment': getattr(self, 'environment', '') or '',
            'onboarding_api_style': style,
            'server_egress_ip': SERVER_EGRESS_IP,
            'request_headers': share_headers,
            'encrypted_body_bytes': encrypted_body_bytes,
            'encrypted_body_base64_preview': encrypted_body_preview,
            'plain_json_request': plain,
            'http_response': {
                'status': response_block.get('http_status'),
                'headers': response_block.get('headers') or {},
                'body': resp_body,
                'latency_ms': latency_ms,
                'transport_error': transport_error,
            },
            'expected_success_response': {
                'status': True,
                'message': 'successful',
                'data': {
                    'merchantStatus': True,
                    'remarks': 'Successfully recorded',
                    'superMerchantId': '<supermerchantId>',
                    'merchantLoginId': '<merchantLoginId>',
                    'errorCodes': None,
                },
                'statusCode': 10000,
            },
            'diagnosis': diagnosis,
        }

        return {
            'captured_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'server_egress_ip': SERVER_EGRESS_IP,
            'share_with_tapits': share,
            'diagnosis': diagnosis,
            'request': {
                'method': method,
                'url': url,
                'mode': mode,
                'headers': self._header_summary(request_headers),
                'encrypted_body_bytes': encrypted_body_bytes,
                'plain_json_scrubbed': plain,
                'note': (
                    'Wire body is AES-encrypted text/xml (PHP path per phpsamplecode.txt). '
                    'plain_json_scrubbed / share_with_tapits.plain_json_request mirrors the doc SAMPLE: '
                    'MD5 merchantLoginPin + base64 image previews (not [REDACTED] placeholders).'
                ),
            },
            'response': response_block,
        }

    def _post_encrypted(
        self,
        url: str,
        payload: dict,
        *,
        device_imei: str | None = None,
        extra_headers: dict | None = None,
        aes_mode: str | None = None,
        content_type: str | None = None,
        mode_label: str | None = None,
    ) -> dict:
        """
        Encrypted POST used by onboarding / eKYC / AEPS.

        aes_mode:
          - 'ecb': Java/.NET path — AEPS_RSA.net sample (AesEngine, no IV)
          - 'cbc': PHP path — phpsamplecode.txt (AES-128-CBC + fixed IV)
        If omitted: auto from URL (`/php/` → CBC + text/xml, else ECB).
        """
        url_l = (url or '').lower()
        is_php_path = '/php/' in url_l
        resolved_mode = (aes_mode or ('cbc' if is_php_path else 'ecb')).lower()
        resolved_ct = content_type
        if resolved_ct is None and is_php_path:
            resolved_ct = 'text/xml'

        plain = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
        enc = build_encrypted_request(
            plain_json=plain,
            rsa_public_key_pem=self.rsa_public_key_pem,
            aes_mode=resolved_mode,
        )
        # Doc Sample Headers: trnTimestamp, hash, eskey (+ deviceIMEI on txn APIs).
        # PHP sample adds Content-Type: text/xml; Java/.NET sample does not set it.
        headers = {
            'trnTimestamp': enc['trnTimestamp'],
            'hash': enc['hash'],
            'eskey': enc['eskey'],
        }
        if resolved_ct:
            headers['Content-Type'] = resolved_ct
        if device_imei:
            headers['deviceIMEI'] = device_imei
        if extra_headers:
            headers.update(extra_headers)

        wire_mode = mode_label or (
            'php_cbc_encrypted' if resolved_mode == 'cbc' else 'java_ecb_encrypted'
        )

        started = time.monotonic()
        try:
            resp = requests.post(url, data=enc['body'], headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            exchange = self._build_exchange(
                method='POST',
                url=url,
                request_headers=headers,
                plain_payload=payload,
                encrypted_body_bytes=len(enc.get('body') or b'') if isinstance(enc.get('body'), (bytes, str)) else None,
                mode=wire_mode,
                transport_error=str(exc),
            )
            raise FingpayClientError(
                f'Fingpay transport error: {exc}',
                payload={'url': url},
                exchange=exchange,
            ) from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        try:
            data = resp.json()
        except Exception:
            data = {'raw': (resp.text or '')[:2000]}

        enc_body_str = enc['body'] if isinstance(enc.get('body'), str) else ''
        exchange = self._build_exchange(
            method='POST',
            url=url,
            request_headers=headers,
            plain_payload=payload,
            encrypted_body_bytes=len(enc['body']) if isinstance(enc.get('body'), (bytes, str)) else None,
            mode=wire_mode,
            resp=resp,
            latency_ms=latency_ms,
            encrypted_body_preview=(
                f'{enc_body_str[:120]}...[base64 truncated, total_len={len(enc_body_str)}]'
                if len(enc_body_str) > 140
                else enc_body_str
            ),
        )

        if resp.status_code >= 400:
            raw_preview = ''
            if isinstance(data, dict):
                raw_preview = str(data.get('raw') or data.get('message') or '')[:200]
            hint = ''
            if resp.status_code == 403:
                hint = (
                    ' Production host blocked this server IP (AWS ELB 403). '
                    'Ask Tapits to whitelist IP 57.131.39.21 on fingpayap.tapits.in '
                    '(docs: IP must be whitelisted before integration). '
                    'This is not a form/credential JSON error — the request never reached Fingpay app.'
                )
            raise FingpayClientError(
                f'Fingpay HTTP {resp.status_code}{hint}',
                status_code=resp.status_code,
                payload={
                    'response': scrub_sensitive(data),
                    'latency_ms': latency_ms,
                    'url': url,
                    'raw_preview': raw_preview,
                    'exchange': exchange,
                },
                exchange=exchange,
            )
        if isinstance(data, dict):
            data['_meta'] = {'latency_ms': latency_ms, 'http_status': resp.status_code}
            data['_exchange'] = exchange
        return data if isinstance(data, dict) else {'data': data, '_meta': {'latency_ms': latency_ms}, '_exchange': exchange}

    def create_merchant(self, merchant_payload: dict, *, latitude, longitude, ip_address: str) -> dict:
        from apps.integrations.fingpay.crypto import trn_timestamp_now

        # IMPORTANT: do NOT put `timestamp` in the JSON body.
        # Observed on UAT+Prod: any body timestamp yields statusCode 10004
        # "error occured in modelCreation" and masks real auth errors (10005).
        # Time goes only in header `trnTimestamp` via _post_encrypted.
        body = {
            'username': self.super_merchant_login_id,
            'password': self.password_md5,
            'latitude': float(latitude),
            'longitude': float(longitude),
            'ipAddress': str(ip_address or '0.0.0.0'),
            'supermerchantId': int(self.super_merchant_id)
            if str(self.super_merchant_id).isdigit()
            else self.super_merchant_id,
            'merchant': merchant_payload,
        }
        # Active admin selection: Java/.NET or PHP create URL + matching AES mode.
        url = self.onboarding_create_url()
        aes_mode = self.onboarding_aes_mode()
        logger.info(
            'Fingpay create_merchant url=%s env=%s style=%s aes=%s login=%s smid=%s companyType=%s state=%s',
            url,
            self.environment or '-',
            self.onboarding_api_style,
            aes_mode,
            (merchant_payload or {}).get('merchantLoginId'),
            body.get('supermerchantId'),
            (merchant_payload or {}).get('companyType'),
            ((merchant_payload or {}).get('merchantAddress') or {}).get('merchantState'),
        )
        return self._post_encrypted(
            url,
            body,
            aes_mode=aes_mode,
            content_type='text/xml' if aes_mode == 'cbc' else None,
            mode_label=f'{self.onboarding_api_style}_{aes_mode}_encrypted',
        )

    def create_merchant_simple(self, merchant_payload: dict, *, latitude, longitude, ip_address: str) -> dict:
        """
        UAT helper: plain JSON onboarding (no AES).
        hash = Base64(SHA256(loginId + '@' + MD5(password)))
        """
        from apps.integrations.fingpay.crypto import sha256_b64, trn_timestamp_now

        # Same rule as PHP path: no body timestamp (causes 10004 modelCreation).
        body = {
            'username': self.super_merchant_login_id,
            'password': self.password_md5,
            'latitude': float(latitude),
            'longitude': float(longitude),
            'ipAddress': str(ip_address or '0.0.0.0'),
            'supermerchantId': int(self.super_merchant_id)
            if str(self.super_merchant_id).isdigit()
            else self.super_merchant_id,
            'merchant': merchant_payload,
        }
        url = f'{self.onboarding_base_url}/api/onboarding/merchant/simple/creation/v2'
        headers = {
            'Content-Type': 'application/json',
            'trnTimestamp': trn_timestamp_now(),
            'hash': sha256_b64(f'{self.super_merchant_login_id}@{self.password_md5}'),
        }
        started = time.monotonic()
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            exchange = self._build_exchange(
                method='POST',
                url=url,
                request_headers=headers,
                plain_payload=body,
                encrypted_body_bytes=None,
                mode='simple_json',
                transport_error=str(exc),
            )
            raise FingpayClientError(
                f'Fingpay transport error: {exc}',
                payload={'url': url},
                exchange=exchange,
            ) from exc
        latency_ms = int((time.monotonic() - started) * 1000)
        try:
            data = resp.json()
        except Exception:
            data = {'raw': (resp.text or '')[:2000]}
        exchange = self._build_exchange(
            method='POST',
            url=url,
            request_headers=headers,
            plain_payload=body,
            encrypted_body_bytes=None,
            mode='simple_json',
            resp=resp,
            latency_ms=latency_ms,
        )
        if resp.status_code >= 400:
            raise FingpayClientError(
                f'Fingpay HTTP {resp.status_code}',
                status_code=resp.status_code,
                payload={'response': scrub_sensitive(data), 'url': url, 'exchange': exchange},
                exchange=exchange,
            )
        if isinstance(data, dict):
            data['_meta'] = {'latency_ms': latency_ms, 'http_status': resp.status_code, 'mode': 'simple'}
            data['_exchange'] = exchange
        return data if isinstance(data, dict) else {'data': data, '_meta': {'latency_ms': latency_ms}, '_exchange': exchange}

    def ekyc_send_otp(self, payload: dict, *, device_imei: str) -> dict:
        url = f'{self.ekyc_base_url}/fpekyc/api/ekyc/merchant/php/sendotp'
        # Doc paths vary; callers may override via full URL helpers below
        return self._post_encrypted(url, payload, device_imei=device_imei)

    def ekyc_post(self, path: str, payload: dict, *, device_imei: str) -> dict:
        url = f'{self.ekyc_base_url.rstrip("/")}/{path.lstrip("/")}'
        return self._post_encrypted(url, payload, device_imei=device_imei)

    def aeps_post(self, path: str, payload: dict, *, device_imei: str) -> dict:
        url = f'{self.aeps_base_url.rstrip("/")}/{path.lstrip("/")}'
        return self._post_encrypted(url, payload, device_imei=device_imei)

    def onboarding_post(self, path: str, payload: dict, *, device_imei: str | None = None) -> dict:
        """POST encrypted to onboarding host (fpaepsweb) — status mid-points live here."""
        url = f'{self.onboarding_base_url.rstrip("/")}/{path.lstrip("/")}'
        return self._post_encrypted(url, payload, device_imei=device_imei)

    def fetch_bank_list(self, url: str) -> Any:
        try:
            resp = requests.get(url, timeout=min(60, self.timeout))
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise FingpayClientError(f'Bank list fetch failed: {exc}') from exc

    def _get_json(self, url: str) -> Any:
        try:
            resp = requests.get(url, timeout=min(60, self.timeout))
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise FingpayClientError(f'Fingpay GET failed ({url}): {exc}') from exc

    def get_onboarding_states(self) -> list[dict]:
        """GET /api/onboarding/getstates → [{stateId, state, stateCode, ...}]"""
        url = f'{self.onboarding_base_url}/api/onboarding/getstates'
        data = self._get_json(url)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            rows = data.get('data') or data.get('states') or []
            return rows if isinstance(rows, list) else []
        return []

    def get_company_types(self) -> list[dict]:
        """GET /api/onboarding/get/companyType/master → [{id, mccCode, mccDescription}]"""
        url = f'{self.onboarding_base_url}/api/onboarding/get/companyType/master'
        data = self._get_json(url)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            rows = data.get('data') or []
            return rows if isinstance(rows, list) else []
        return []

    def verify_recon_hash(self, *, request_body: str, provided_hash: str) -> bool:
        if not self.secret_key:
            raise FingpayClientError(
                'Provider secret_key missing — required to verify 3-way recon hash '
                '(ask Fingpay Integration Team by email).'
            )
        expected = build_recon_hash(
            request_body=request_body,
            super_merchant_login_id=self.super_merchant_login_id,
            secret_key=self.secret_key,
        )
        return expected == (provided_hash or '').strip()
