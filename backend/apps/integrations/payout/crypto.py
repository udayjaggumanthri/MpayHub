"""
AES-GCM encrypt/decrypt for Vidual / VimoPay payloads.

Matches their Python sample (pycryptodome):
  key = encryptdecryptKey UTF-8 bytes
  nonce/iv = saltKey UTF-8 bytes
  output = Base64(ciphertext || 16-byte tag)
"""
from __future__ import annotations

import base64
import logging

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from apps.integrations.payout.exceptions import PayoutCryptoError

logger = logging.getLogger(__name__)

_TAG_LEN = 16


def _key_iv_bytes(ed_key: str, iv_key: str) -> tuple[bytes, bytes]:
    key = (ed_key or '').encode('utf-8')
    iv = (iv_key or '').encode('utf-8')
    if len(key) not in (16, 24, 32):
        raise PayoutCryptoError(
            f'AES key length must be 16, 24, or 32 bytes; got {len(key)}'
        )
    if not iv:
        raise PayoutCryptoError('AES IV/nonce (saltKey) is required')
    return key, iv


def encrypt(plain_text: str, *, ed_key: str, iv_key: str) -> str:
    """Encrypt plaintext → Base64(ciphertext + tag)."""
    try:
        key, iv = _key_iv_bytes(ed_key, iv_key)
        plain_bytes = (plain_text or '').encode('utf-8')
        encryptor = Cipher(algorithms.AES(key), modes.GCM(iv)).encryptor()
        ciphertext = encryptor.update(plain_bytes) + encryptor.finalize()
        return base64.b64encode(ciphertext + encryptor.tag).decode('utf-8')
    except PayoutCryptoError:
        raise
    except Exception as exc:
        logger.exception('VimoPay encrypt failed')
        raise PayoutCryptoError(f'Encrypt failed: {exc}') from exc


def decrypt(encrypted_text: str, *, ed_key: str, iv_key: str) -> str:
    """Decrypt Base64(ciphertext + tag) → plaintext."""
    try:
        key, iv = _key_iv_bytes(ed_key, iv_key)
        blob = base64.b64decode(encrypted_text or '')
        if len(blob) < _TAG_LEN:
            raise PayoutCryptoError('Ciphertext too short')
        ciphertext, tag = blob[:-_TAG_LEN], blob[-_TAG_LEN:]
        decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag)).decryptor()
        plain = decryptor.update(ciphertext) + decryptor.finalize()
        return plain.decode('utf-8').strip().strip('\r\n\0')
    except PayoutCryptoError:
        raise
    except Exception as exc:
        logger.exception('VimoPay decrypt failed')
        raise PayoutCryptoError(f'Decrypt failed: {exc}') from exc
