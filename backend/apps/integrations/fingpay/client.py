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


class FingpayClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class FingpayClient:
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

    def _post_encrypted(
        self,
        url: str,
        payload: dict,
        *,
        device_imei: str | None = None,
        extra_headers: dict | None = None,
    ) -> dict:
        plain = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
        enc = build_encrypted_request(plain_json=plain, rsa_public_key_pem=self.rsa_public_key_pem)
        # PHP sample (phpsamplecode.txt) sends text/xml with AES-CBC body
        headers = {
            'Content-Type': 'text/xml',
            'trnTimestamp': enc['trnTimestamp'],
            'hash': enc['hash'],
            'eskey': enc['eskey'],
        }
        if device_imei:
            headers['deviceIMEI'] = device_imei
        if extra_headers:
            headers.update(extra_headers)

        started = time.monotonic()
        try:
            resp = requests.post(url, data=enc['body'], headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise FingpayClientError(f'Fingpay transport error: {exc}') from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        try:
            data = resp.json()
        except Exception:
            data = {'raw': (resp.text or '')[:2000]}

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
                },
            )
        if isinstance(data, dict):
            data['_meta'] = {'latency_ms': latency_ms, 'http_status': resp.status_code}
        return data if isinstance(data, dict) else {'data': data, '_meta': {'latency_ms': latency_ms}}

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
        url = f'{self.onboarding_base_url}/api/onboarding/merchant/php/creation/v2'
        logger.info(
            'Fingpay create_merchant url=%s login=%s smid=%s companyType=%s state=%s',
            url,
            (merchant_payload or {}).get('merchantLoginId'),
            body.get('supermerchantId'),
            (merchant_payload or {}).get('companyType'),
            ((merchant_payload or {}).get('merchantAddress') or {}).get('merchantState'),
        )
        return self._post_encrypted(url, body)

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
            raise FingpayClientError(f'Fingpay transport error: {exc}') from exc
        latency_ms = int((time.monotonic() - started) * 1000)
        try:
            data = resp.json()
        except Exception:
            data = {'raw': (resp.text or '')[:2000]}
        if isinstance(data, dict):
            data['_meta'] = {'latency_ms': latency_ms, 'http_status': resp.status_code, 'mode': 'simple'}
        return data if isinstance(data, dict) else {'data': data, '_meta': {'latency_ms': latency_ms}}

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
