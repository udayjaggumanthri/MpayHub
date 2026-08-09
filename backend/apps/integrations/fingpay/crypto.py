"""
Fingpay request encryption helpers.

Aligned with AEPS docs + PHP sample (phpsamplecode.txt):
- AES-128-CBC with fixed IV 06f2f04cc530364f
- Session key RSA-encrypted with Fingpay X.509 certificate / public key (eskey)
- hash = Base64(SHA256(plain JSON bytes))
"""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

# From Fingpay PHP sample code shipped in AEPS docs
PHP_AES_IV = b'06f2f04cc530364f'

BUNDLED_CERT_PATH = Path(__file__).resolve().parent / 'assets' / 'fingpay_public_production.cer'


def load_bundled_fingpay_certificate() -> str:
    """Return PEM text of the Fingpay public certificate shipped with the integration docs."""
    if BUNDLED_CERT_PATH.is_file():
        return BUNDLED_CERT_PATH.read_text(encoding='utf-8').strip() + '\n'
    return ''


def sha256_b64(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode('utf-8')
    digest = hashlib.sha256(data).digest()
    return base64.b64encode(digest).decode('ascii')


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def generate_aes128_session_key() -> bytes:
    from os import urandom

    return urandom(16)


def _load_rsa_public_key(pem_or_der: str | bytes):
    """
    Accepts:
    - X.509 certificate PEM (BEGIN CERTIFICATE) — as in fingpay_public_production.cer
    - Public key PEM (BEGIN PUBLIC KEY / BEGIN RSA PUBLIC KEY)
    - Raw base64 SPKI DER
    """
    raw = pem_or_der if isinstance(pem_or_der, bytes) else pem_or_der.encode('utf-8')
    text = raw.decode('utf-8', errors='ignore').strip()

    if 'BEGIN CERTIFICATE' in text:
        cert = x509.load_pem_x509_certificate(text.encode('utf-8'), backend=default_backend())
        return cert.public_key()

    if 'BEGIN' in text:
        try:
            return serialization.load_pem_public_key(text.encode('utf-8'), backend=default_backend())
        except Exception:
            # Some kits ship CERT without clear labels after copy/paste noise
            pass

    # Assume base64-encoded DER certificate or SPKI
    try:
        der = base64.b64decode(''.join(text.split()))
        try:
            cert = x509.load_der_x509_certificate(der, backend=default_backend())
            return cert.public_key()
        except Exception:
            return serialization.load_der_public_key(der, backend=default_backend())
    except Exception as exc:
        raise ValueError(
            'Invalid Fingpay public key/certificate. Paste the full PEM including '
            '-----BEGIN CERTIFICATE----- / -----END CERTIFICATE----- '
            '(from fingpay_public_production.cer in the AEPS docs).'
        ) from exc


def encrypt_session_key_rsa(session_key: bytes, public_key_pem: str) -> str:
    public_key = _load_rsa_public_key(public_key_pem)
    encrypted = public_key.encrypt(session_key, padding.PKCS1v15())
    return base64.b64encode(encrypted).decode('ascii')


def encrypt_aes_cbc_pkcs7(session_key: bytes, plaintext: bytes | str, *, iv: bytes = PHP_AES_IV) -> str:
    """PHP openssl_encrypt AES-128-CBC + PKCS7 (default openssl padding)."""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode('utf-8')
    if len(session_key) != 16:
        raise ValueError('AES-128 session key must be 16 bytes')
    if len(iv) != 16:
        raise ValueError('AES IV must be 16 bytes')
    padder = PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(session_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode('ascii').replace('\r', '').replace('\n', '')


def encrypt_aes_ecb_pkcs7(session_key: bytes, plaintext: bytes | str) -> str:
    """Java/.NET BC-style AES-128-ECB + PKCS7 (non-PHP endpoints if required)."""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode('utf-8')
    padder = PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(session_key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode('ascii').replace('\r', '').replace('\n', '')


def trn_timestamp_now() -> str:
    return datetime.now().strftime('%d/%m/%Y %H:%M:%S')


def build_encrypted_request(
    *,
    plain_json: str,
    rsa_public_key_pem: str,
    aes_mode: str = 'cbc',
) -> dict[str, str]:
    """
    Returns headers/body pieces: hash, eskey, body, trnTimestamp.

    aes_mode:
      - 'cbc' (default): PHP sample /php/ APIs
      - 'ecb': Java/.NET sample style
    """
    session_key = generate_aes128_session_key()
    if (aes_mode or 'cbc').lower() == 'ecb':
        body = encrypt_aes_ecb_pkcs7(session_key, plain_json)
    else:
        body = encrypt_aes_cbc_pkcs7(session_key, plain_json)
    return {
        'trnTimestamp': trn_timestamp_now(),
        'hash': sha256_b64(plain_json),
        'eskey': encrypt_session_key_rsa(session_key, rsa_public_key_pem),
        'body': body,
    }


def build_recon_hash(*, request_body: str, super_merchant_login_id: str, secret_key: str) -> str:
    """hash = Base64(SHA256(requestbody + supermerchantLoginId + secretKey))."""
    material = f'{request_body}{super_merchant_login_id}{secret_key}'
    return sha256_b64(material)


def scrub_sensitive(obj: Any, *, for_tapits: bool = False) -> Any:
    """
    Redact secrets for logs/UI.

    for_tapits=True keeps Tapits-facing share packs close to the doc SAMPLE REQUEST:
    - merchantLoginPin shown when it is already an MD5 hex (32 chars)
    - KYC images shown as truncated base64 previews (same style as the PDF sample)
    - full Aadhaar still masked
    """
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
        'merchantloginpin',
        'password',
        'secretkey',
        'photobase64',
    }
    IMAGE_KEYS = {
        'merchantpanimage',
        'maskedaadharimage',
        'maskedaadhaarimage',
        'backgroundimageofshop',
    }

    def _looks_md5(val: Any) -> bool:
        s = str(val or '')
        return len(s) == 32 and all(c in '0123456789abcdef' for c in s.lower())

    def _image_preview(val: Any) -> str:
        s = str(val or '')
        if len(s) <= 120:
            return s
        # Match Fingpay PDF sample style: short base64 prefix (single line)
        return f'{s[:96]}...[base64 truncated for email, full image sent on wire, total_len={len(s)}]'

    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key_l = str(k).lower().replace('_', '')
            # Image fields first — maskedAadharImage contains "aadhar" substring
            if key_l in IMAGE_KEYS or ('image' in key_l and isinstance(v, str) and len(v) > 80):
                if for_tapits and isinstance(v, str) and len(v) > 40:
                    out[k] = _image_preview(v)
                elif isinstance(v, str) and len(v) > 80:
                    out[k] = f'[BASE64_IMAGE len={len(v)}]'
                else:
                    out[k] = scrub_sensitive(v, for_tapits=for_tapits)
            elif key_l in ('merchantloginpin', 'merchantpin', 'password') and for_tapits and _looks_md5(v):
                # Doc SAMPLE REQUEST shows MD5 hex for password/merchantLoginPin — share that form
                out[k] = str(v)
            elif key_l in ('aadhaarnumber', 'aadharnumber') and for_tapits:
                out[k] = mask_aadhaar(v)
            elif key_l in SENSITIVE or 'pid' in key_l or 'aadhaar' in key_l or 'aadhar' in key_l:
                out[k] = '[REDACTED]'
            else:
                out[k] = scrub_sensitive(v, for_tapits=for_tapits)
        return out
    if isinstance(obj, list):
        return [scrub_sensitive(x, for_tapits=for_tapits) for x in obj]
    return obj


def mask_aadhaar(value: str | None) -> str:
    digits = ''.join(c for c in str(value or '') if c.isdigit())
    if len(digits) < 4:
        return 'xxxxxxxxxxxx'
    return f'xxxxxxxx{digits[-4:]}'
