"""VimoPay (Vidual) payout adapter — AES-GCM request/response, authorize token, masters, callback."""
from __future__ import annotations

import json
import logging
import re
import time
from decimal import Decimal
from typing import Any

import requests

from apps.integrations.models import ApiMaster
from apps.integrations.payout import crypto as vimopay_crypto
from apps.integrations.payout.exceptions import (
    PayoutConfigurationError,
    PayoutInitiateError,
    PayoutNotSupportedError,
)
from apps.integrations.payout.port import PayoutProvider
from apps.integrations.payout.types import (
    DOMAIN_FAILED,
    MasterItem,
    PayoutCallbackEvent,
    PayoutInitiateRequest,
    PayoutInitiateResult,
    map_provider_status_code,
)

logger = logging.getLogger(__name__)

DEFAULT_PATHS = {
    'authorize': '/payoutapi/api/signature/authorizeuat',
    'bank_list': '/masterapi/api/master/banklistuat',
    'state_list': '/masterapi/api/master/statelistuat',
    'purpose_list': '/masterapi/api/master/purposelistuat',
    'payout': '/payoutapi/api/payment/payoutsuat',
}

_TITLE_PREFIX = re.compile(
    r'^(?:mr|mrs|ms|miss|dr|prof|sir|smt|shri|sri)\.?\s+',
    re.IGNORECASE,
)


def sanitize_beneficiary_name(name: str) -> str:
    """
    VimoPay: beneficiaryName must be alphabets and spaces only, 2–100 chars.
    Strip titles (Mr./Mrs.), drop digits/punctuation, collapse spaces.
    """
    text = str(name or '').strip()
    # Remove common honorifics repeatedly
    for _ in range(3):
        nxt = _TITLE_PREFIX.sub('', text).strip()
        if nxt == text:
            break
        text = nxt
    # Keep letters and spaces only (Unicode letters for Indian names)
    cleaned = ''.join(ch if (ch.isalpha() or ch.isspace()) else ' ' for ch in text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned[:100]


def _extract_validation_messages(decrypted: Any) -> str:
    """Turn Vidual validation arrays into a readable message."""
    if isinstance(decrypted, list):
        parts = []
        for row in decrypted:
            if isinstance(row, dict):
                msg = str(row.get('ErrorMessage') or row.get('errorMessage') or '').strip()
                members = row.get('MemberNames') or row.get('memberNames') or []
                if msg and members:
                    parts.append(f"{', '.join(str(m) for m in members)}: {msg}")
                elif msg:
                    parts.append(msg)
        if parts:
            return '; '.join(parts)
    if isinstance(decrypted, dict):
        msg = str(
            decrypted.get('responseMessage')
            or decrypted.get('message')
            or decrypted.get('ErrorMessage')
            or ''
        ).strip()
        if msg:
            return msg
    if isinstance(decrypted, str) and decrypted.strip():
        return decrypted.strip()[:500]
    return ''



class VimopayPayoutProvider(PayoutProvider):
    def __init__(self, *, master: ApiMaster, secrets: dict[str, Any]):
        self.master = master
        self.secrets = secrets or {}
        self.config = master.config_json if isinstance(master.config_json, dict) else {}
        self.base_url = (master.base_url or '').rstrip('/')
        if not self.base_url:
            raise PayoutConfigurationError('VimoPay base_url is required on ApiMaster.')

        self.secret_key = str(self.secrets.get('secret_key') or '').strip()
        self.salt_key = str(self.secrets.get('salt_key') or '').strip()
        self.ed_key = str(
            self.secrets.get('encrypt_decrypt_key')
            or self.secrets.get('encryptdecryptKey')
            or ''
        ).strip()
        self.user_id = str(self.secrets.get('user_id') or self.secrets.get('userId') or '').strip()
        if not all([self.secret_key, self.salt_key, self.ed_key, self.user_id]):
            raise PayoutConfigurationError(
                'VimoPay requires secret_key, salt_key, encrypt_decrypt_key, and user_id.'
            )

        # Payload AES-GCM: UAT gateway encrypts with secretKey + saltKey (not encryptdecryptKey).
        # encryptdecryptKey is still required on authorize headers per Vidual docs.
        # Override via config_json.crypto_key_source = "encrypt_decrypt_key" if a future env differs.
        crypto_src = str(self.config.get('crypto_key_source') or 'secret_key').strip().lower()
        if crypto_src in ('encrypt_decrypt_key', 'encryptdecryptkey', 'ed'):
            self.payload_key = self.ed_key
        else:
            self.payload_key = self.secret_key
        self.payload_iv = self.salt_key

        self.timeout = max(5, min(int(self.config.get('timeout') or 30), 90))
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        token_ttl = int(self.config.get('token_ttl_seconds') or 300)
        self._token_ttl = max(60, min(token_ttl, 3600))

    @property
    def provider_code(self) -> str:
        return self.master.provider_code or 'vimopay'

    def amount_limits(self) -> tuple[Decimal, Decimal]:
        # Spec: min ₹100; callback docs imply below ₹1 lakh. Overridable via config_json.
        cfg = self.config if isinstance(self.config, dict) else {}
        try:
            mn = Decimal(str(cfg.get('min_amount') or '100'))
        except Exception:
            mn = Decimal('100')
        try:
            mx = Decimal(str(cfg.get('max_amount') or '100000'))
        except Exception:
            mx = Decimal('100000')
        return mn, mx

    def supported_transfer_modes(self) -> frozenset[str]:
        return frozenset({'IMPS', 'NEFT'})

    def normalize_beneficiary_name(self, name: str) -> str:
        return sanitize_beneficiary_name(name)

    def _path(self, key: str) -> str:
        overrides = self.config.get('paths') if isinstance(self.config.get('paths'), dict) else {}
        return str(overrides.get(key) or DEFAULT_PATHS[key])

    def _url(self, key: str) -> str:
        return f'{self.base_url}{self._path(key)}'

    def _encrypt(self, plain: str) -> str:
        return vimopay_crypto.encrypt(plain, ed_key=self.payload_key, iv_key=self.payload_iv)

    def _decrypt(self, cipher: str) -> str:
        return vimopay_crypto.decrypt(cipher, ed_key=self.payload_key, iv_key=self.payload_iv)

    def _decrypt_data_field(self, data: Any) -> Any:
        """Decrypt envelope `data` when it is a ciphertext string; pass through lists/dicts."""
        if data is None:
            return None
        if isinstance(data, (list, dict)):
            return data
        text = str(data).strip()
        if not text:
            return text
        # Already looks like JSON
        if text.startswith('{') or text.startswith('['):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        try:
            plain = self._decrypt(text)
            if plain.startswith('{') or plain.startswith('['):
                return json.loads(plain)
            return plain
        except Exception:
            # Token from authorize is used opaque as Bearer — return as-is if decrypt fails
            return text

    def authorize(self) -> str:
        """POST authorizeuat; return opaque Bearer token (Postman uses raw `data` blob)."""
        headers = {
            'secretKey': self.secret_key,
            'saltKey': self.salt_key,
            'encryptdecryptKey': self.ed_key,
            'userId': self.user_id,
            'Content-Type': 'application/json',
        }
        resp = requests.post(self._url('authorize'), headers=headers, json={}, timeout=self.timeout)
        try:
            body = resp.json()
        except ValueError as exc:
            raise PayoutInitiateError(
                f'Authorize returned non-JSON (HTTP {resp.status_code})',
                code='authorize_bad_response',
                details={'status_code': resp.status_code, 'text': resp.text[:500]},
            ) from exc

        if not body.get('successStatus') and str(body.get('responseCode') or '') != '000':
            raise PayoutInitiateError(
                str(body.get('message') or 'Authorization failed'),
                code=str(body.get('responseCode') or 'authorize_failed'),
                details=body,
            )
        token = body.get('data')
        if not token or not isinstance(token, str):
            raise PayoutInitiateError(
                'Authorization response missing token data',
                code='authorize_no_token',
                details=body,
            )
        self._token = token.strip()
        self._token_expires_at = time.time() + self._token_ttl
        return self._token

    def _bearer(self) -> str:
        if self._token and time.time() < self._token_expires_at - 15:
            return self._token
        return self.authorize()

    def _auth_headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self._bearer()}',
            'userId': self.user_id,
            'userid': self.user_id,
            'Content-Type': 'application/json',
        }

    def _get_master(self, path_key: str) -> list[MasterItem]:
        resp = requests.get(
            self._url(path_key),
            headers=self._auth_headers(),
            timeout=self.timeout,
        )
        try:
            body = resp.json()
        except ValueError as exc:
            raise PayoutInitiateError(
                f'{path_key} returned non-JSON (HTTP {resp.status_code})',
                code='master_bad_response',
                details={'status_code': resp.status_code},
            ) from exc

        data = self._decrypt_data_field(body.get('data'))
        if isinstance(data, dict) and 'data' in data:
            data = data['data']
        if not isinstance(data, list):
            raise PayoutInitiateError(
                f'{path_key} did not return a list',
                code='master_bad_shape',
                details={'body_keys': list(body.keys()) if isinstance(body, dict) else []},
            )
        items: list[MasterItem] = []
        for row in data:
            if not isinstance(row, dict):
                continue
            code = str(row.get('code') or '').strip()
            desc = str(row.get('description') or '').strip()
            if code:
                items.append(MasterItem(code=code, description=desc or code))
        return items

    def list_banks(self) -> list[MasterItem]:
        return self._get_master('bank_list')

    def list_states(self) -> list[MasterItem]:
        return self._get_master('state_list')

    def list_purposes(self) -> list[MasterItem]:
        return self._get_master('purpose_list')

    def initiate(self, request: PayoutInitiateRequest) -> PayoutInitiateResult:
        mode = (request.payment_mode or 'IMPS').strip().lower()
        if mode not in ('imps', 'neft'):
            raise PayoutInitiateError(
                'VimoPay supports IMPS and NEFT only',
                code='003',
            )
        beneficiary_name = sanitize_beneficiary_name(request.beneficiary_name)
        if len(beneficiary_name) < 2:
            raise PayoutInitiateError(
                'Beneficiary name must contain only letters and spaces (at least 2 characters). '
                'Remove titles like Mr./Mrs. and special characters.',
                code='003',
            )
        location = (request.beneficiary_location or '').strip().upper()
        payload = {
            'amount': float(request.amount),
            'merchantRefId': request.merchant_ref_id,
            'beneficiaryBank': request.beneficiary_bank_code,
            'paymentPurpose': request.payment_purpose or '004',
            'paymentMode': mode,
            'beneficiaryAccountNumber': request.beneficiary_account_number,
            'beneficiaryIFSC': request.beneficiary_ifsc,
            'beneficiaryMobileNumber': request.beneficiary_mobile,
            'beneficiaryName': beneficiary_name,
            'beneficiaryLocation': location,
            'lat': str(request.lat or '28.7041'),
            'long': str(request.long or '77.1025'),
            'udf1': request.udf1 or '',
            'udf2': request.udf2 or '',
            'udf3': request.udf3 or '',
        }
        plain = json.dumps(payload, separators=(',', ':'))
        encrypted = self._encrypt(plain)
        # Postman uses lowercase requestbody
        body = {'requestbody': encrypted}

        resp = requests.post(
            self._url('payout'),
            headers=self._auth_headers(),
            json=body,
            timeout=self.timeout,
        )
        try:
            envelope = resp.json()
        except ValueError as exc:
            raise PayoutInitiateError(
                f'Payout returned non-JSON (HTTP {resp.status_code})',
                code='payout_bad_response',
                details={'status_code': resp.status_code, 'text': resp.text[:500]},
            ) from exc

        # Top-level validation failure — decrypt data for a useful message
        top_code = str(envelope.get('responseCode') or '')
        if envelope.get('successStatus') is False and top_code not in ('', '000', '004', '002'):
            detail_msg = ''
            decrypted = None
            raw_data = envelope.get('data')
            if isinstance(raw_data, str) and raw_data.strip():
                try:
                    decrypted = self._decrypt_data_field(raw_data)
                    if isinstance(decrypted, str) and (
                        decrypted.startswith('{') or decrypted.startswith('[')
                    ):
                        decrypted = json.loads(decrypted)
                    detail_msg = _extract_validation_messages(decrypted)
                except Exception:
                    decrypted = None
            raise PayoutInitiateError(
                detail_msg or str(envelope.get('message') or 'Payout rejected'),
                code=top_code or 'payout_rejected',
                details={'envelope': envelope, 'decrypted': decrypted},
            )

        data = self._decrypt_data_field(envelope.get('data'))
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {'raw': data}
        if not isinstance(data, dict):
            data = {'raw': data}

        status_code = str(
            data.get('txnStatusCode')
            or data.get('responseCode')
            or top_code
            or '004'
        )
        txn_status = str(data.get('txnStatus') or '')
        domain = map_provider_status_code(status_code, txn_status=txn_status)
        if domain == DOMAIN_FAILED:
            raise PayoutInitiateError(
                str(data.get('responseMessage') or envelope.get('message') or 'Payout failed'),
                code=status_code,
                details={'envelope': envelope, 'data': data},
            )

        charges = data.get('charges')
        try:
            charges_dec = Decimal(str(charges)) if charges is not None and str(charges) != '' else None
        except Exception:
            charges_dec = None

        return PayoutInitiateResult(
            domain_status=domain,
            provider_status_code=status_code,
            provider_txn_id=str(data.get('txnId') or ''),
            response_message=str(data.get('responseMessage') or envelope.get('message') or ''),
            charges=charges_dec,
            raw={
                'envelope': envelope,
                'data': data,
                'request_plain_keys': list(payload.keys()),
                'beneficiaryName_sent': beneficiary_name,
            },
        )

    def parse_callback(self, raw: dict[str, Any] | list | str | bytes) -> PayoutCallbackEvent:
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode('utf-8', errors='replace')
        if isinstance(raw, str):
            raw = json.loads(raw) if raw.strip() else {}
        if not isinstance(raw, dict):
            raise PayoutInitiateError('Callback payload must be a JSON object', code='bad_callback')

        # Some gateways wrap encrypted body — try decrypt if requestbody present
        payload = raw
        for key in ('requestbody', 'requestBody', 'data'):
            if key in raw and isinstance(raw[key], str) and len(raw[key]) > 40 and key != 'data':
                try:
                    plain = self._decrypt(raw[key])
                    payload = json.loads(plain)
                    break
                except Exception:
                    pass
            if key == 'data' and isinstance(raw.get('data'), str):
                try:
                    decrypted = self._decrypt_data_field(raw['data'])
                    if isinstance(decrypted, dict):
                        payload = decrypted
                        break
                except Exception:
                    pass

        merchant_ref = str(
            payload.get('merchantRefId')
            or payload.get('merchant_ref_id')
            or ''
        ).strip()
        status_code = str(payload.get('txnStatusCode') or payload.get('responseCode') or '').strip()
        txn_status = str(payload.get('txnStatus') or '').strip()
        domain = map_provider_status_code(status_code, txn_status=txn_status)

        amount = payload.get('amount')
        charges = payload.get('charges')
        try:
            amount_dec = Decimal(str(amount)) if amount is not None and str(amount) != '' else None
        except Exception:
            amount_dec = None
        try:
            charges_dec = Decimal(str(charges)) if charges is not None and str(charges) != '' else None
        except Exception:
            charges_dec = None

        return PayoutCallbackEvent(
            merchant_ref_id=merchant_ref,
            domain_status=domain,
            provider_status_code=status_code or map_provider_status_code('', txn_status=txn_status),
            provider_txn_id=str(payload.get('txnId') or ''),
            rrn=str(payload.get('rrn') or payload.get('RRN') or ''),
            response_message=str(payload.get('responseMessage') or ''),
            amount=amount_dec,
            charges=charges_dec,
            payment_mode=str(payload.get('paymentMode') or ''),
            raw=payload if isinstance(payload, dict) else {'raw': payload},
        )

    def inquire_status(self, merchant_ref_id: str) -> PayoutCallbackEvent:
        raise PayoutNotSupportedError(
            f'VimoPay has no status-inquiry API for {merchant_ref_id}'
        )

    def test_connection(self) -> dict[str, Any]:
        try:
            token = self.authorize()
            return {
                'ok': True,
                'detail': 'VimoPay authorizeuat succeeded',
                'token_preview': (token[:12] + '…') if token and len(token) > 12 else '***',
            }
        except Exception as exc:
            return {'ok': False, 'detail': str(exc)}
