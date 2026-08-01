"""
Fingpay request encryption helpers (AES-128 session key + RSA public key + SHA-256 hash).

Matches Fingpay Services API Doc encryption flow used across onboarding / eKYC / product APIs.
"""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


def sha256_b64(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode('utf-8')
    digest = hashlib.sha256(data).digest()
    return base64.b64encode(digest).decode('ascii')


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def generate_aes128_session_key() -> bytes:
    # 16 bytes = AES-128
    from os import urandom

    return urandom(16)


def _load_rsa_public_key(pem_or_der: str | bytes):
    raw = pem_or_der if isinstance(pem_or_der, bytes) else pem_or_der.encode('utf-8')
    text = raw.decode('utf-8', errors='ignore').strip()
    if 'BEGIN' not in text:
        # Assume base64-encoded DER SPKI
        try:
            der = base64.b64decode(text)
            return serialization.load_der_public_key(der, backend=default_backend())
        except Exception:
            pass
        # Wrap as PEM
        lines = '\n'.join(text[i : i + 64] for i in range(0, len(text), 64))
        text = f'-----BEGIN PUBLIC KEY-----\n{lines}\n-----END PUBLIC KEY-----'
        raw = text.encode('utf-8')
    return serialization.load_pem_public_key(raw, backend=default_backend())


def encrypt_session_key_rsa(session_key: bytes, public_key_pem: str) -> str:
    public_key = _load_rsa_public_key(public_key_pem)
    encrypted = public_key.encrypt(session_key, padding.PKCS1v15())
    return base64.b64encode(encrypted).decode('ascii')


def encrypt_aes_pkcs7(session_key: bytes, plaintext: bytes | str) -> str:
    if isinstance(plaintext, str):
        plaintext = plaintext.encode('utf-8')
    padder = PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    # Fingpay samples use AES ECB with PKCS7 (legacy BC provider style)
    cipher = Cipher(algorithms.AES(session_key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode('ascii').replace('\r', '').replace('\n', '')


def trn_timestamp_now() -> str:
    # Doc samples: 29/11/2017 15:24:47
    return datetime.now().strftime('%d/%m/%Y %H:%M:%S')


def build_encrypted_request(
    *,
    plain_json: str,
    rsa_public_key_pem: str,
) -> dict[str, str]:
    """
    Returns headers/body pieces:
      hash, eskey, body, trnTimestamp
    """
    session_key = generate_aes128_session_key()
    return {
        'trnTimestamp': trn_timestamp_now(),
        'hash': sha256_b64(plain_json),
        'eskey': encrypt_session_key_rsa(session_key, rsa_public_key_pem),
        'body': encrypt_aes_pkcs7(session_key, plain_json),
    }


def build_recon_hash(*, request_body: str, super_merchant_login_id: str, secret_key: str) -> str:
    """hash = Base64(SHA256(requestbody + supermerchantLoginId + secretKey))."""
    material = f'{request_body}{super_merchant_login_id}{secret_key}'
    return sha256_b64(material)


def scrub_sensitive(obj: Any) -> Any:
    """Recursively scrub Aadhaar / PID-like keys from dicts for audit storage."""
    SENSITIVE = {
        'aadhaar',
        'aadhar',
        'aadharnumber',
        'aadhaarnumber',
        'piddata',
        'pid',
        'captureresponse',
        'hmac',
        'sessionkey',
        'merchantpin',
        'password',
        'secretkey',
        'photobase64',
    }
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key_l = str(k).lower().replace('_', '')
            if key_l in SENSITIVE or 'pid' in key_l or 'aadhaar' in key_l or 'aadhar' in key_l:
                out[k] = '[REDACTED]'
            else:
                out[k] = scrub_sensitive(v)
        return out
    if isinstance(obj, list):
        return [scrub_sensitive(x) for x in obj]
    return obj


def mask_aadhaar(value: str | None) -> str:
    digits = ''.join(c for c in str(value or '') if c.isdigit())
    if len(digits) < 4:
        return 'xxxxxxxxxxxx'
    return f'xxxxxxxx{digits[-4:]}'
