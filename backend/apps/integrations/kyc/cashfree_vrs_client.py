"""
Low-level HTTP client for Cashfree Verification (VRS) APIs.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urljoin

import requests

from apps.integrations.kyc.exceptions import KycProviderError, KycVerificationFailed
from apps.integrations.kyc.verification_id import assert_cashfree_verification_id

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15


def _verification_base(base_url: str) -> str:
    root = str(base_url or '').strip().rstrip('/')
    if not root:
        raise KycProviderError('Cashfree base URL is not configured.')
    if root.endswith('/verification'):
        return root
    return f'{root}/verification'


def _headers(client_id: str, client_secret: str) -> dict[str, str]:
    return {
        'x-client-id': str(client_id or '').strip(),
        'x-client-secret': str(client_secret or '').strip(),
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


def _parse_json(resp: requests.Response) -> dict:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {'data': data}
    except ValueError:
        return {'message': resp.text[:500]}


def _raise_for_error(resp: requests.Response, *, action: str) -> None:
    if 200 <= resp.status_code < 300:
        return
    body = _parse_json(resp)
    msg = str(body.get('message') or body.get('error') or f'{action} failed')
    code = str(body.get('code') or resp.status_code)
    if resp.status_code in (400, 422):
        raise KycVerificationFailed(msg, code=code, details=body)
    raise KycProviderError(msg)


class CashfreeVrsClient:
    def __init__(
        self,
        *,
        base_url: str,
        client_id: str,
        client_secret: str,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.base_url = _verification_base(base_url)
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = max(3, min(int(timeout or DEFAULT_TIMEOUT), 45))
        self._headers = _headers(client_id, client_secret)

    def post(self, path: str, payload: dict, *, action: str) -> dict:
        url = urljoin(f'{self.base_url}/', path.lstrip('/'))
        try:
            resp = requests.post(url, json=payload, headers=self._headers, timeout=self.timeout)
        except requests.RequestException as e:
            logger.warning('Cashfree %s request failed: %s', action, e)
            raise KycProviderError(f'Unable to reach verification service. Please try again.') from e
        _raise_for_error(resp, action=action)
        return _parse_json(resp)

    def get(self, path: str, *, params: Optional[dict] = None, action: str) -> dict:
        url = urljoin(f'{self.base_url}/', path.lstrip('/'))
        try:
            resp = requests.get(url, params=params or {}, headers=self._headers, timeout=self.timeout)
        except requests.RequestException as e:
            logger.warning('Cashfree %s request failed: %s', action, e)
            raise KycProviderError('Unable to reach verification service. Please try again.') from e
        _raise_for_error(resp, action=action)
        return _parse_json(resp)

    def verify_pan_sync(self, *, pan: str, name: str) -> dict:
        return self.post('pan', {'pan': pan, 'name': name}, action='PAN verify')

    def verify_pan_advance(self, *, pan: str, name: str, verification_id: str) -> dict:
        vid = assert_cashfree_verification_id(verification_id)
        return self.post(
            'pan/advance',
            {'pan': pan, 'name': name, 'verification_id': vid},
            action='PAN 360',
        )

    def digilocker_verify_account(self, *, verification_id: str, aadhaar_number: str) -> dict:
        return self.post(
            'digilocker/verify-account',
            {'verification_id': verification_id, 'aadhaar_number': aadhaar_number},
            action='DigiLocker verify account',
        )

    def digilocker_create_url(
        self,
        *,
        verification_id: str,
        document_requested: list[str],
        redirect_url: str,
        user_flow: str,
    ) -> dict:
        payload: dict[str, Any] = {
            'verification_id': verification_id,
            'document_requested': document_requested,
        }
        if redirect_url:
            payload['redirect_url'] = redirect_url
        if user_flow:
            payload['user_flow'] = user_flow
        return self.post('digilocker', payload, action='DigiLocker create URL')

    def digilocker_get_status(self, *, verification_id: str = '', reference_id: str = '') -> dict:
        params = {}
        if verification_id:
            params['verification_id'] = verification_id
        if reference_id:
            params['reference_id'] = reference_id
        return self.get('digilocker', params=params, action='DigiLocker status')

    def digilocker_get_document(self, *, document_type: str, verification_id: str = '', reference_id: str = '') -> dict:
        params = {}
        if verification_id:
            params['verification_id'] = verification_id
        if reference_id:
            params['reference_id'] = reference_id
        path = f'digilocker/document/{document_type}'
        return self.get(path, params=params, action='DigiLocker document')

    def verify_bank_account_sync(
        self,
        *,
        bank_account: str,
        ifsc: str,
        name: str = '',
        phone: str = '',
    ) -> dict:
        payload: dict[str, Any] = {
            'bank_account': bank_account,
            'ifsc': ifsc.upper(),
        }
        if name:
            payload['name'] = name
        if phone:
            payload['phone'] = phone
        return self.post('bank-account/sync', payload, action='Bank account verify')
