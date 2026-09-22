"""Uber CMS crypto — launch payload encryption + inbound hash verification.

Launch encryption mirrors the Web URL doc (CryptoJS AES-ECB + PKCS7, then
double Base64). Key length is data-driven (16/24/32) after Base64-decoding
superMerchantSkey.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from apps.integrations.fingpay.crypto import scrub_sensitive, sha256_b64


def decode_skey(super_merchant_skey: str) -> bytes:
    """Base64-decode the CMS skey; accept raw 16/24/32-byte keys as fallback."""
    raw = str(super_merchant_skey or '').strip()
    if not raw:
        raise ValueError('superMerchantSkey is required')
    try:
        key = base64.b64decode(raw)
    except Exception:
        key = raw.encode('utf-8')
    if len(key) not in (16, 24, 32):
        # Doc sample placeholder keys can be odd lengths — pad/truncate to AES-128
        # only as last resort for local tests; production keys must be 16/24/32.
        if len(key) < 16:
            key = key.ljust(16, b'\0')
        elif len(key) < 24:
            key = key[:16]
        elif len(key) < 32:
            key = key[:24]
        else:
            key = key[:32]
    return key


def encrypt_aes_ecb_pkcs7_var(session_key: bytes, plaintext: bytes | str) -> str:
    """AES-ECB + PKCS7 with variable key length (AES-128/192/256)."""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode('utf-8')
    if len(session_key) not in (16, 24, 32):
        raise ValueError('AES key must be 16, 24, or 32 bytes')
    padder = PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(session_key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode('ascii').replace('\r', '').replace('\n', '')


def encrypt_launch_payload(payload: dict[str, Any], *, super_merchant_skey: str) -> str:
    """
    Match Web URL doc:
      encryptInfo = btoa(CryptoJS.AES.encrypt(JSON.stringify(payload), keyWordArray, ECB/PKCS7).toString())
    With a WordArray key, CryptoJS emits unsalted Base64 ciphertext; window.btoa wraps it again.
    """
    key = decode_skey(super_merchant_skey)
    plain = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
    inner_b64 = encrypt_aes_ecb_pkcs7_var(key, plain)
    # Double Base64 — outer wrap mirrors window.btoa(inner_b64_string)
    return base64.b64encode(inner_b64.encode('ascii')).decode('ascii')


def build_inbound_hash(
    raw_body: str,
    secret_key: str,
    *,
    template: str = '{payload}{secret_key}',
) -> str:
    """hash = Base64(SHA256(template.format(payload=raw_body, secret_key=secret_key)))."""
    material = (template or '{payload}{secret_key}').format(
        payload=raw_body or '',
        secret_key=secret_key or '',
    )
    return sha256_b64(material)


def verify_inbound_hash(
    raw_body: str,
    secret_key: str,
    provided_hash: str,
    *,
    template: str = '{payload}{secret_key}',
) -> bool:
    expected = build_inbound_hash(raw_body, secret_key, template=template)
    return hmac.compare_digest(expected, (provided_hash or '').strip())


def build_launch_url(
    *,
    cms_base_url: str,
    login_path: str,
    encrypted_data: str,
    skey: str,
) -> str:
    base = (cms_base_url or '').rstrip('/')
    path = login_path or '/UberCMSBC/#/login'
    if not path.startswith('/'):
        path = '/' + path
    # Hash-routing: query string must follow the #/login fragment as in the doc sample.
    if '#/' in path:
        return f'{base}{path}?data={encrypted_data}&skey={skey}'
    return f'{base}{path}?data={encrypted_data}&skey={skey}'


def scrub_cms(obj: Any) -> Any:
    return scrub_sensitive(obj, for_tapits=False)
