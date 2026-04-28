import base64
import binascii
import hashlib
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


def _decode_maybe_hex(secret: str) -> bytes:
    text = str(secret or '').strip()
    if not text:
        return b''
    if len(text) % 2 == 0:
        try:
            raw = binascii.unhexlify(text)
            if raw:
                return raw
        except (binascii.Error, ValueError):
            pass
    return text.encode('utf-8')


def _normalize_key_bytes(working_key: str) -> bytes:
    raw = _decode_maybe_hex(working_key)
    # BillAvenue working key is typically AES-128 material.
    if len(raw) >= 16:
        return raw[:16]
    return raw.ljust(16, b'0')


def _normalize_iv_bytes(iv: str) -> bytes:
    raw = _decode_maybe_hex(iv)
    if len(raw) >= 16:
        return raw[:16]
    return raw.ljust(16, b'0')

def derive_aes128_key(working_key: str, *, mode: str = 'rawhex') -> bytes:
    """
    Derive 16-byte AES key material from BillAvenue working key.

    - rawhex: decode hex (or UTF-8) and take first 16 bytes (legacy behavior in this codebase)
    - md5: AES key = MD5 digest bytes of the working_key string (matches common PHP samples)
    """
    m = str(mode or 'rawhex').strip().lower()
    if m in ('raw', 'rawhex', 'hex'):
        return _normalize_key_bytes(working_key)
    if m == 'md5':
        raw = str(working_key or '').strip()
        return hashlib.md5(raw.encode('utf-8')).digest()
    return _normalize_key_bytes(working_key)


def _encrypt_bytes(plain_text: str, *, working_key: str, iv: str, key_derivation: str = 'rawhex') -> bytes:
    key = derive_aes128_key(working_key, mode=key_derivation)
    iv_b = _normalize_iv_bytes(iv)
    padder = padding.PKCS7(128).padder()
    padded = padder.update((plain_text or '').encode('utf-8')) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv_b), backend=default_backend())
    enc_ctx = cipher.encryptor()
    enc = enc_ctx.update(padded) + enc_ctx.finalize()
    return enc


def encrypt_payload(
    plain_text: str,
    *,
    working_key: str,
    iv: str,
    key_derivation: str = 'rawhex',
    output_encoding: str = 'base64',
) -> str:
    enc = _encrypt_bytes(plain_text, working_key=working_key, iv=iv, key_derivation=key_derivation)
    out = str(output_encoding or 'base64').strip().lower()
    if out in ('hex', 'bin2hex'):
        return enc.hex()
    return base64.b64encode(enc).decode('utf-8')


def decrypt_payload(
    cipher_text: str,
    *,
    working_key: str,
    iv: str,
    key_derivation: str = 'rawhex',
    input_encoding: str = 'base64',
) -> str:
    key = derive_aes128_key(working_key, mode=key_derivation)
    iv_b = _normalize_iv_bytes(iv)
    enc = str(input_encoding or 'base64').strip().lower()
    if enc in ('hex',):
        cipher_data = bytes.fromhex((cipher_text or '').strip())
    else:
        cipher_data = base64.b64decode(cipher_text or '')
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv_b), backend=default_backend())
    dec = cipher.decryptor().update(cipher_data) + cipher.decryptor().finalize()
    unpadder = padding.PKCS7(128).unpadder()
    unpadded = unpadder.update(dec) + unpadder.finalize()
    return unpadded.decode('utf-8')


def decrypt_payload_auto(cipher_text: str, *, working_key: str, iv: str, key_derivation: str = 'rawhex') -> str:
    """
    Try common encodings for provider responses:
    - base64 ciphertext (common)
    - hex ciphertext (some gateways/samples)
    """
    last = None
    for enc in ('base64', 'hex'):
        try:
            return decrypt_payload(cipher_text, working_key=working_key, iv=iv, key_derivation=key_derivation, input_encoding=enc)
        except Exception as e:
            last = e
    raise last or ValueError('Unable to decrypt payload')
