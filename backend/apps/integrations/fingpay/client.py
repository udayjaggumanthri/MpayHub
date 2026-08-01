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
        headers = {
            'Content-Type': 'text/plain',
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
            raise FingpayClientError(
                f'Fingpay HTTP {resp.status_code}',
                status_code=resp.status_code,
                payload={'response': scrub_sensitive(data), 'latency_ms': latency_ms},
            )
        if isinstance(data, dict):
            data['_meta'] = {'latency_ms': latency_ms, 'http_status': resp.status_code}
        return data if isinstance(data, dict) else {'data': data, '_meta': {'latency_ms': latency_ms}}

    def create_merchant(self, merchant_payload: dict, *, latitude, longitude, ip_address: str) -> dict:
        body = {
            'username': self.super_merchant_login_id,
            'password': self.password_md5,
            'timestamp': None,
            'latitude': float(latitude),
            'longitude': float(longitude),
            'ipAddress': ip_address,
            'supermerchantId': int(self.super_merchant_id) if str(self.super_merchant_id).isdigit() else self.super_merchant_id,
            'merchant': merchant_payload,
        }
        # timestamp format per doc samples often string; include both styles via merchant layer
        from apps.integrations.fingpay.crypto import trn_timestamp_now

        body['timestamp'] = trn_timestamp_now()
        url = f'{self.onboarding_base_url}/api/onboarding/merchant/php/creation/v2'
        return self._post_encrypted(url, body)

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

    def fetch_bank_list(self, url: str) -> Any:
        try:
            resp = requests.get(url, timeout=min(60, self.timeout))
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise FingpayClientError(f'Bank list fetch failed: {exc}') from exc

    def verify_recon_hash(self, *, request_body: str, provided_hash: str) -> bool:
        expected = build_recon_hash(
            request_body=request_body,
            super_merchant_login_id=self.super_merchant_login_id,
            secret_key=self.secret_key,
        )
        return expected == (provided_hash or '').strip()
