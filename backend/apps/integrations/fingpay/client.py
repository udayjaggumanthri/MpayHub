"""
Thin HTTP client for Fingpay AEPS APIs.

Supports encrypted (AES + RSA eskey) and Simple (plain JSON) modes.
Endpoint paths are resolved from an admin-editable map.
"""
from __future__ import annotations

import json
import logging
import time
from urllib.parse import urlparse
from typing import Any, Callable

import requests

from apps.integrations.fingpay.crypto import (
    build_encrypted_request,
    build_recon_hash,
    build_simple_onboarding_hash,
    build_simple_txn_hash,
    build_status_check_hash,
    md5_hex,
    resolve_password_md5,
    scrub_sensitive,
    trn_timestamp_now,
    trn_timestamp_simple,
)
from apps.integrations.fingpay.netinfo import resolve_egress_ip
from apps.integrations.fingpay.endpoints import (
    DEFAULT_EGRESS_IP,
    PRODUCT_PATH_KEYS,
    default_endpoints_for,
    merge_endpoints,
)

logger = logging.getLogger(__name__)

# Backward-compatible alias; prefer client.egress_ip
SERVER_EGRESS_IP = DEFAULT_EGRESS_IP

AuditCallback = Callable[..., None]


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
        'simple': '/api/onboarding/merchant/simple/creation/v2',
    }

    def __init__(
        self,
        *,
        super_merchant_id: str,
        super_merchant_login_id: str,
        password_plain: str = '',
        secret_key: str,
        rsa_public_key_pem: str,
        onboarding_base_url: str,
        ekyc_base_url: str,
        aeps_base_url: str,
        recon_base_url: str = '',
        timeout: int = 180,
        onboarding_api_style: str = 'java',
        environment: str = '',
        api_mode: str = 'encrypted',
        endpoints: dict | None = None,
        egress_ip: str = '',
        debug_mode: bool = False,
        audit_callback: AuditCallback | None = None,
        bank_list_url: str = '',
        aadhaar_pay_bank_list_url: str = '',
        password_mode: str = 'plain',
        password_md5: str = '',
    ):
        self.super_merchant_id = str(super_merchant_id)
        self.super_merchant_login_id = super_merchant_login_id
        self.password_mode = (password_mode or 'plain').lower()
        if password_md5:
            self.password_md5 = resolve_password_md5(password_md5, mode='md5')
        else:
            self.password_md5 = resolve_password_md5(password_plain or '', mode=self.password_mode)
        self.secret_key = secret_key or ''
        self.rsa_public_key_pem = rsa_public_key_pem or ''
        self.onboarding_base_url = (onboarding_base_url or '').rstrip('/')
        self.ekyc_base_url = (ekyc_base_url or '').rstrip('/')
        self.aeps_base_url = (aeps_base_url or '').rstrip('/')
        self.recon_base_url = (recon_base_url or '').rstrip('/')
        self.bank_list_url = bank_list_url or ''
        self.aadhaar_pay_bank_list_url = aadhaar_pay_bank_list_url or ''
        self.timeout = max(30, int(timeout or 180))
        self.environment = (environment or '').lower()
        mode = (api_mode or 'encrypted').lower()
        if self.environment == 'simple':
            mode = 'simple'
        self.api_mode = mode if mode in ('encrypted', 'simple') else 'encrypted'
        style = (onboarding_api_style or 'java').lower()
        if self.api_mode == 'simple':
            self.onboarding_api_style = 'simple'
        else:
            self.onboarding_api_style = style if style in ('java', 'php') else 'java'
        self.endpoints = merge_endpoints(
            endpoints,
            environment=self.environment or ('simple' if self.api_mode == 'simple' else 'prod'),
            onboarding_api_style=self.onboarding_api_style if self.onboarding_api_style != 'simple' else 'php',
        )
        self.egress_ip = (egress_ip or '').strip()
        self.debug_mode = bool(debug_mode)
        self.audit_callback = audit_callback
        self._detected_outbound_ipv4: str | None = None

    def _egress_ip_for_onboarding_payload(self) -> str:
        """
        Fingpay onboarding create expects `ipAddress` (and allowlists depend on it).
        Prefer the detected outbound IPv4 over the stored egress_ip, which goes
        stale whenever the host moves.
        """
        if self._detected_outbound_ipv4:
            return self._detected_outbound_ipv4

        self._detected_outbound_ipv4 = resolve_egress_ip(
            self.egress_ip,
            url=self.onboarding_base_url or self.aeps_base_url or '',
        )
        return self._detected_outbound_ipv4

    @property
    def effective_egress_ip(self) -> str:
        """Best known outbound IP for support context and whitelist diagnosis."""
        return self._egress_ip_for_onboarding_payload() or self.egress_ip

    def endpoint(self, key: str, default: str = '') -> str:
        return str(self.endpoints.get(key) or default or '')

    def onboarding_create_url(self) -> str:
        if self.api_mode == 'simple' or self.onboarding_api_style == 'simple':
            path = self.endpoint('onboarding_create_simple', self.ONBOARDING_CREATE_PATHS['simple'])
        elif self.onboarding_api_style == 'php':
            path = self.endpoint('onboarding_create_php', self.ONBOARDING_CREATE_PATHS['php'])
        else:
            path = self.endpoint('onboarding_create_java', self.ONBOARDING_CREATE_PATHS['java'])
        return self._join(self.onboarding_base_url, path)

    def onboarding_aes_mode(self) -> str:
        return 'cbc' if self.onboarding_api_style == 'php' else 'ecb'

    def product_path(self, product: str) -> str:
        key = PRODUCT_PATH_KEYS.get(product, product.lower())
        return self.endpoint(key)

    def _join(self, base: str, path: str) -> str:
        """Join base + path, or return path unchanged when it is already an absolute URL."""
        p = (path or '').strip()
        if p.startswith('http://') or p.startswith('https://'):
            return p
        b = (base or '').rstrip('/')
        if not p:
            return b
        if not b:
            return p
        return f'{b}/{p.lstrip("/")}'

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
        raw_request_body: Any = None,
    ) -> dict:
        response_block: dict[str, Any] = {
            'transport_error': transport_error,
            'latency_ms': latency_ms,
        }
        raw_resp_body: Any = None
        if resp is not None:
            try:
                body = resp.json()
                raw_resp_body = body
            except Exception:
                body = {'raw_html_or_text': (resp.text or '')[:4000]}
                raw_resp_body = body
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
        egress = self.effective_egress_ip
        if http_status == 403 and str(response_block.get('headers', {}).get('server') or '').lower().startswith(
            'awselb'
        ):
            diagnosis = (
                f'AWS ELB returned HTTP 403 before the Fingpay app. '
                f'Source IP {egress} is still blocked. '
                'Whitelist is NOT effective yet for this host/IP.'
            )
        elif transport_error:
            diagnosis = f'Transport failure: {transport_error}'
        elif http_status and int(http_status) >= 400:
            diagnosis = f'HTTP {http_status} from Fingpay edge/app.'
        else:
            sc = None
            if isinstance(raw_resp_body, dict):
                sc = raw_resp_body.get('statusCode')
            if str(sc) == '10015':
                diagnosis = (
                    f'Fingpay statusCode 10015 — IP whitelist pending for egress {egress}. '
                    'Ask Tapits to whitelist this IP for the active host/supermerchant.'
                )
            else:
                diagnosis = 'Reached Fingpay application layer (inspect statusCode/message).'

        plain = scrub_sensitive(plain_payload or {}, for_tapits=True)
        resp_body = response_block.get('body')
        if isinstance(resp_body, (dict, list)):
            resp_body = scrub_sensitive(resp_body, for_tapits=True)
        share_headers = {str(k): str(v or '') for k, v in (request_headers or {}).items()}
        style = self.onboarding_api_style
        share = {
            'endpoint': f'{method} {url}',
            'doc': (
                f'Fingpay API — mode={self.api_mode}, style={style}, env={self.environment}. '
                f'encryption='
                f'{"none (simple plain JSON)" if self.api_mode == "simple" else ("AES-128-CBC" if style == "php" else "AES-128-ECB")}.'
            ),
            'environment': self.environment,
            'api_mode': self.api_mode,
            'onboarding_api_style': style,
            'server_egress_ip': egress,
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
            'diagnosis': diagnosis,
        }

        return {
            'captured_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'server_egress_ip': egress,
            'share_with_tapits': share,
            'diagnosis': diagnosis,
            'debug_mode': self.debug_mode,
            'raw_request_body': raw_request_body if self.debug_mode else None,
            'raw_response_body': raw_resp_body if self.debug_mode else None,
            'request': {
                'method': method,
                'url': url,
                'mode': mode,
                'headers': self._header_summary(request_headers),
                'encrypted_body_bytes': encrypted_body_bytes,
                'plain_json_scrubbed': plain,
            },
            'response': response_block,
        }

    def _emit_audit(
        self,
        *,
        endpoint: str,
        method: str,
        exchange: dict,
        success: bool,
        error_message: str = '',
        merchant_tran_id: str = '',
        user=None,
    ) -> None:
        if not self.audit_callback:
            return
        try:
            self.audit_callback(
                endpoint=endpoint,
                method=method,
                exchange=exchange,
                success=success,
                error_message=error_message,
                merchant_tran_id=merchant_tran_id,
                user=user,
                debug_mode=self.debug_mode,
            )
        except Exception:
            logger.exception('AEPS audit callback failed')

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
        endpoint_label: str | None = None,
        merchant_tran_id: str = '',
        user=None,
    ) -> dict:
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
        label = endpoint_label or url

        started = time.monotonic()
        try:
            resp = requests.post(url, data=enc['body'], headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            exchange = self._build_exchange(
                method='POST',
                url=url,
                request_headers=headers,
                plain_payload=payload,
                encrypted_body_bytes=len(enc.get('body') or '') if isinstance(enc.get('body'), (bytes, str)) else None,
                mode=wire_mode,
                transport_error=str(exc),
                raw_request_body=payload,
            )
            self._emit_audit(
                endpoint=label,
                method='POST',
                exchange=exchange,
                success=False,
                error_message=str(exc),
                merchant_tran_id=merchant_tran_id,
                user=user,
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
            raw_request_body=payload,
        )

        ok = resp.status_code < 400 and (
            not isinstance(data, dict)
            or data.get('status') is True
            or str(data.get('statusCode')) == '10000'
        )
        self._emit_audit(
            endpoint=label,
            method='POST',
            exchange=exchange,
            success=bool(ok),
            error_message='' if ok else str((data or {}).get('message') or f'HTTP {resp.status_code}')[:500],
            merchant_tran_id=merchant_tran_id or str((payload or {}).get('merchantTranId') or ''),
            user=user,
        )

        if resp.status_code >= 400:
            raw_preview = ''
            if isinstance(data, dict):
                raw_preview = str(data.get('raw') or data.get('message') or '')[:200]
            hint = ''
            if resp.status_code == 403:
                hint = (
                    f' Host blocked this server IP (AWS ELB 403). '
                    f'Ask Tapits to whitelist IP {self.effective_egress_ip}.'
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
            data['_meta'] = {'latency_ms': latency_ms, 'http_status': resp.status_code, 'mode': self.api_mode}
            data['_exchange'] = exchange
        return data if isinstance(data, dict) else {'data': data, '_meta': {'latency_ms': latency_ms}, '_exchange': exchange}

    def _post_simple(
        self,
        url: str,
        payload: dict,
        *,
        headers: dict,
        body_text: str | None = None,
        mode_label: str = 'simple_json',
        endpoint_label: str | None = None,
        merchant_tran_id: str = '',
        user=None,
    ) -> dict:
        label = endpoint_label or url
        # Hash must match the exact bytes Fingpay receives — compact JSON, no spaces.
        wire_body = body_text if body_text is not None else json.dumps(
            payload, separators=(',', ':'), ensure_ascii=False
        )
        started = time.monotonic()
        try:
            resp = requests.post(
                url,
                data=wire_body.encode('utf-8'),
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            exchange = self._build_exchange(
                method='POST',
                url=url,
                request_headers=headers,
                plain_payload=payload,
                encrypted_body_bytes=None,
                mode=mode_label,
                transport_error=str(exc),
                raw_request_body=payload,
            )
            self._emit_audit(
                endpoint=label,
                method='POST',
                exchange=exchange,
                success=False,
                error_message=str(exc),
                merchant_tran_id=merchant_tran_id,
                user=user,
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
            plain_payload=payload,
            encrypted_body_bytes=None,
            mode=mode_label,
            resp=resp,
            latency_ms=latency_ms,
            raw_request_body=payload,
        )
        ok = resp.status_code < 400 and (
            not isinstance(data, dict)
            or data.get('status') is True
            or str(data.get('statusCode')) == '10000'
        )
        self._emit_audit(
            endpoint=label,
            method='POST',
            exchange=exchange,
            success=bool(ok),
            error_message='' if ok else str((data or {}).get('message') or f'HTTP {resp.status_code}')[:500],
            merchant_tran_id=merchant_tran_id or str((payload or {}).get('merchantTranId') or ''),
            user=user,
        )
        if resp.status_code >= 400:
            provider_msg = ''
            if isinstance(data, dict):
                provider_msg = str(data.get('message') or data.get('errorMessage') or '')
            raise FingpayClientError(
                provider_msg or f'Fingpay HTTP {resp.status_code}',
                status_code=resp.status_code,
                payload={'response': scrub_sensitive(data), 'url': url, 'exchange': exchange},
                exchange=exchange,
            )
        if isinstance(data, dict):
            data['_meta'] = {'latency_ms': latency_ms, 'http_status': resp.status_code, 'mode': 'simple'}
            data['_exchange'] = exchange
        return data if isinstance(data, dict) else {'data': data, '_meta': {'latency_ms': latency_ms}, '_exchange': exchange}

    def post(
        self,
        url: str,
        payload: dict,
        *,
        device_imei: str | None = None,
        hash_style: str = 'txn',
        endpoint_label: str | None = None,
        merchant_tran_id: str = '',
        user=None,
        aes_mode: str | None = None,
        content_type: str | None = None,
        timestamp_style: str = 'simple',
        include_body_timestamp: bool = True,
    ) -> dict:
        """
        Unified POST: encrypted or simple based on api_mode.

        hash_style:
          - 'txn': Base64(SHA256(json + secretKey + trnTimestamp)) for simple
          - 'onboarding': Base64(SHA256(login@md5password)) for simple create
          - 'status': status-check hash (caller should pass prebuilt headers via status_check)

        timestamp_style:
          - 'simple': YYYY-MM-DD HH:MM:SS (eKYC / onboarding)
          - 'aeps': dd/MM/yyyy HH:mm:ss (Mini Statement / 2FA / product sample headers)

        include_body_timestamp:
          Mini Statement / product samples put timestamp in the JSON body.
          The 2FA 2.1 sample does not — header trnTimestamp is still sent.
        """
        if self.api_mode == 'simple':
            ts = trn_timestamp_now() if timestamp_style == 'aeps' else trn_timestamp_simple()
            # Keep body.timestamp identical to header trnTimestamp (Mini Statement / product docs).
            # Assign in place so documented JSON key order is preserved for the hash.
            if isinstance(payload, dict) and timestamp_style == 'aeps' and include_body_timestamp:
                payload = dict(payload)
                payload['timestamp'] = ts
            plain = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
            if hash_style == 'onboarding':
                hdr_hash = build_simple_onboarding_hash(
                    super_merchant_login_id=self.super_merchant_login_id,
                    password_md5=self.password_md5,
                )
            else:
                if not self.secret_key:
                    raise FingpayClientError(
                        'Provider secret_key missing — required for Simple API txn/eKYC/2FA hash.'
                    )
                hdr_hash = build_simple_txn_hash(
                    plain_json=plain,
                    secret_key=self.secret_key,
                    trn_timestamp=ts,
                )
            headers = {
                'Content-Type': 'text/json',
                'trnTimestamp': ts,
                'hash': hdr_hash,
            }
            if device_imei:
                headers['deviceIMEI'] = device_imei
            return self._post_simple(
                url,
                payload,
                headers=headers,
                body_text=plain,
                endpoint_label=endpoint_label,
                merchant_tran_id=merchant_tran_id,
                user=user,
            )
        return self._post_encrypted(
            url,
            payload,
            device_imei=device_imei,
            aes_mode=aes_mode,
            content_type=content_type,
            endpoint_label=endpoint_label,
            merchant_tran_id=merchant_tran_id,
            user=user,
        )

    def create_merchant(self, merchant_payload: dict, *, latitude, longitude, ip_address: str) -> dict:
        payload_ip = self._egress_ip_for_onboarding_payload()
        body = {
            'username': self.super_merchant_login_id,
            'password': self.password_md5,
            'latitude': float(latitude),
            'longitude': float(longitude),
            # Always send the real outbound IPv4 for onboarding allowlists.
            # Keep `ip_address` only as a last-resort fallback.
            'ipAddress': str(payload_ip or ip_address or self.egress_ip or '0.0.0.0'),
            'supermerchantId': int(self.super_merchant_id)
            if str(self.super_merchant_id).isdigit()
            else self.super_merchant_id,
            'merchant': merchant_payload,
        }
        url = self.onboarding_create_url()
        logger.info(
            'Fingpay create_merchant url=%s env=%s mode=%s style=%s login=%s smid=%s',
            url,
            self.environment or '-',
            self.api_mode,
            self.onboarding_api_style,
            (merchant_payload or {}).get('merchantLoginId'),
            body.get('supermerchantId'),
        )
        if self.api_mode == 'simple' or self.onboarding_api_style == 'simple':
            return self.post(
                url,
                body,
                hash_style='onboarding',
                endpoint_label='onboarding/create',
            )
        aes_mode = self.onboarding_aes_mode()
        return self.post(
            url,
            body,
            hash_style='txn',
            endpoint_label='onboarding/create',
            aes_mode=aes_mode,
            content_type='text/xml' if aes_mode == 'cbc' else None,
        )

    def create_merchant_simple(self, merchant_payload: dict, *, latitude, longitude, ip_address: str) -> dict:
        """Explicit Simple onboarding (also used when api_mode=simple)."""
        prev_mode = self.api_mode
        self.api_mode = 'simple'
        try:
            return self.create_merchant(
                merchant_payload,
                latitude=latitude,
                longitude=longitude,
                ip_address=ip_address,
            )
        finally:
            self.api_mode = prev_mode

    def ekyc_send_otp(self, payload: dict, *, device_imei: str) -> dict:
        path = self.endpoint('ekyc_send_otp', 'fpekyc/api/ekyc/merchant/php/sendotp')
        url = self._join(self.ekyc_base_url, path)
        return self.post(url, payload, device_imei=device_imei, endpoint_label='ekyc/sendotp')

    def ekyc_post(self, path: str, payload: dict, *, device_imei: str, endpoint_key: str = '') -> dict:
        resolved = self.endpoint(endpoint_key, path) if endpoint_key else path
        url = self._join(self.ekyc_base_url, resolved)
        return self.post(url, payload, device_imei=device_imei, endpoint_label=endpoint_key or path)

    def aeps_post(
        self,
        path: str,
        payload: dict,
        *,
        device_imei: str,
        endpoint_key: str = '',
        include_body_timestamp: bool = True,
    ) -> dict:
        resolved = self.endpoint(endpoint_key, path) if endpoint_key else path
        url = self._join(self.aeps_base_url, resolved)
        return self.post(
            url,
            payload,
            device_imei=device_imei,
            endpoint_label=endpoint_key or path,
            merchant_tran_id=str((payload or {}).get('merchantTranId') or ''),
            timestamp_style='aeps',
            include_body_timestamp=include_body_timestamp,
        )

    def onboarding_post(self, path: str, payload: dict, *, device_imei: str | None = None, endpoint_key: str = '') -> dict:
        resolved = self.endpoint(endpoint_key, path) if endpoint_key else path
        url = self._join(self.onboarding_base_url, resolved)
        return self.post(
            url,
            payload,
            device_imei=device_imei,
            endpoint_label=endpoint_key or path,
            merchant_tran_id=str((payload or {}).get('merchantTranId') or ''),
        )

    def status_check(
        self,
        path: str,
        payload: dict,
        *,
        merchant_tran_id: str,
        merchant_login_id: str,
        device_imei: str | None = None,
        endpoint_key: str = '',
    ) -> dict:
        """Status mid-point — uses status-check hash formula on simple mode."""
        resolved = self.endpoint(endpoint_key, path) if endpoint_key else path
        url = self._join(self.onboarding_base_url, resolved)
        if self.api_mode == 'simple':
            ts = trn_timestamp_simple()
            headers = {
                'Content-Type': 'text/json',
                'trnTimestamp': ts,
                'hash': build_status_check_hash(
                    merchant_tran_id=merchant_tran_id,
                    merchant_login_id=merchant_login_id,
                    super_merchant_login_id=self.super_merchant_login_id,
                ),
            }
            if device_imei:
                headers['deviceIMEI'] = device_imei
            plain = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
            return self._post_simple(
                url,
                payload,
                headers=headers,
                body_text=plain,
                endpoint_label=endpoint_key or path,
                merchant_tran_id=merchant_tran_id,
            )
        return self.onboarding_post(resolved, payload, device_imei=device_imei, endpoint_key=endpoint_key)

    def fetch_bank_list(self, url: str | None = None) -> Any:
        target = url or self.bank_list_url
        if not target:
            path = self.endpoint('banks_aeps', 'fpaepsservice/api/bankdata/bank/details')
            target = self._join(self.aeps_base_url, path)
        try:
            resp = requests.get(target, timeout=min(60, self.timeout))
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
        path = self.endpoint('onboarding_states', '/api/onboarding/getstates')
        url = self._join(self.onboarding_base_url, path)
        data = self._get_json(url)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            rows = data.get('data') or data.get('states') or []
            return rows if isinstance(rows, list) else []
        return []

    def get_company_types(self) -> list[dict]:
        path = self.endpoint('onboarding_company_types', '/api/onboarding/get/companyType/master')
        url = self._join(self.onboarding_base_url, path)
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
