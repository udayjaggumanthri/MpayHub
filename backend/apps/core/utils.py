"""
Utility functions for the mPayhub platform.
"""
from __future__ import annotations

import random
import string
from datetime import datetime
import json
from typing import Optional

from django.conf import settings


def generate_service_id(transaction_type):
    """
    Generate a unique service ID for transactions.
    
    Format:
    - Pay In: PMPI{YYYYMMDD}{random_number}
    - Pay Out: PMPO{YYYYMMDD}{random_number}
    - BBPS: PMBBPS{YYYYMMDD}{random_number}
    """
    date_str = datetime.now().strftime('%Y%m%d')
    random_number = ''.join(random.choices(string.digits, k=5))
    
    prefix_map = {
        'payin': 'PMPI',
        'payout': 'PMPO',
        'bbps': 'PMBBPS',
        'load_money': 'PMLM',
        'wallet_transfer': 'PMWT',
    }
    
    prefix = prefix_map.get(transaction_type.lower(), 'PMTX')
    return f"{prefix}{date_str}{random_number}"


def generate_user_id(role, existing_user_ids):
    """
    Generate a sequential user ID based on role.
    
    Format:
    - Admin: ADMIN{number}
    - Super Distributor: SD{number}
    - Master Distributor: MD{number}
    - Distributor: DT{number}
    - Retailer: R{number}
    """
    role_prefix_map = {
        'Admin': 'ADMIN',
        'Super Distributor': 'SD',
        'Master Distributor': 'MD',
        'Distributor': 'DT',
        'Retailer': 'R',
    }
    
    prefix = role_prefix_map.get(role, 'USER')
    
    # Extract existing numbers for this role
    existing_numbers = []
    for user_id in existing_user_ids:
        # Skip None values
        if user_id is None:
            continue
        if user_id.startswith(prefix):
            try:
                number = int(user_id[len(prefix):])
                existing_numbers.append(number)
            except ValueError:
                continue
    
    # Get next sequential number
    next_number = max(existing_numbers) + 1 if existing_numbers else 1
    
    return f"{prefix}{next_number}"


def generate_otp(length=6):
    """Generate a random OTP of specified length."""
    return ''.join(random.choices(string.digits, k=length))


def format_currency(amount):
    """Format amount as Indian currency."""
    return f"₹{amount:,.2f}"


def format_account_number(account_number):
    """Format account number showing only last 4 digits."""
    if len(account_number) <= 4:
        return account_number
    return f"****{account_number[-4:]}"


def validate_phone(phone):
    """Validate Indian phone number (10 digits)."""
    if not phone:
        return False
    phone = str(phone).strip()
    return phone.isdigit() and len(phone) == 10


def validate_email(email):
    """Basic email validation."""
    if not email:
        return False
    return '@' in email and '.' in email.split('@')[1]


def validate_pan(pan):
    """Validate PAN format (5 letters, 4 digits, 1 letter)."""
    if not pan:
        return False
    pan = str(pan).upper().strip()
    if len(pan) != 10:
        return False
    return pan[:5].isalpha() and pan[5:9].isdigit() and pan[9].isalpha()


def validate_aadhaar(aadhaar):
    """Validate Aadhaar number (12 digits)."""
    if not aadhaar:
        return False
    aadhaar = str(aadhaar).strip()
    return aadhaar.isdigit() and len(aadhaar) == 12


def validate_ifsc(ifsc):
    """Validate IFSC code (4 letters, 0, 5 alphanumeric)."""
    if not ifsc:
        return False
    ifsc = str(ifsc).upper().strip()
    if len(ifsc) != 11:
        return False
    return ifsc[:4].isalpha() and ifsc[4] == '0' and ifsc[5:].isalnum()


def validate_mpin(mpin):
    """Validate MPIN (6 digits)."""
    if not mpin:
        return False
    mpin = str(mpin).strip()
    return mpin.isdigit() and len(mpin) == 6


def _fernet_key_bytes_from_secret_string(secret: str) -> bytes:
    """Derive a urlsafe-b64 Fernet key (32 bytes) from an arbitrary secret string."""
    import base64
    import hashlib

    key_material = hashlib.sha256(str(secret).encode()).digest()
    return base64.urlsafe_b64encode(key_material)


def _legacy_mpin_fernet_key_from_secret_key() -> bytes:
    """Historical MPIN key: SHA256(Django SECRET_KEY) → Fernet-compatible bytes."""
    import base64
    import hashlib

    from django.conf import settings

    key_material = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(key_material)


def _mpin_fernet_key_from_mpin_env() -> Optional[bytes]:
    from django.conf import settings

    raw = (getattr(settings, 'MPIN_ENCRYPTION_KEY', None) or '').strip()
    if not raw:
        return None
    return _fernet_key_bytes_from_secret_string(raw)


def _mpin_fernet_key_from_encryption_key_env() -> Optional[bytes]:
    """
    Optional separate env string (not used for *new* MPIN encryption).

    Included only as a decrypt fallback for environments that briefly encrypted MPINs using this setting.
    """
    from django.conf import settings

    raw = (getattr(settings, 'ENCRYPTION_KEY', None) or '').strip()
    if not raw:
        return None
    return _fernet_key_bytes_from_secret_string(raw)


def _mpin_decrypt_fernet_key_candidates() -> list[bytes]:
    """Keys to try when decrypting stored MPINs (order matters)."""
    keys: list[bytes] = []
    k_mpin = _mpin_fernet_key_from_mpin_env()
    if k_mpin is not None:
        keys.append(k_mpin)
    keys.append(_legacy_mpin_fernet_key_from_secret_key())
    k_enc = _mpin_fernet_key_from_encryption_key_env()
    if k_enc is not None and k_enc not in keys:
        keys.append(k_enc)
    return keys


def _get_encryption_key():
    """
    Fernet key for **encrypting** new MPIN values.

    Uses ``MPIN_ENCRYPTION_KEY`` when set; otherwise the legacy SHA256(``SECRET_KEY``) derivation.
    ``ENCRYPTION_KEY`` is intentionally not used for encryption so template ``.env`` values do not
    break existing MPIN hashes that were always created with the SECRET_KEY-based key.
    """
    k = _mpin_fernet_key_from_mpin_env()
    if k is not None:
        return k
    return _legacy_mpin_fernet_key_from_secret_key()


def encrypt_mpin(mpin):
    """
    Encrypt MPIN using Fernet symmetric encryption.
    """
    from cryptography.fernet import Fernet
    
    key = _get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(mpin.encode())
    return encrypted.decode()


def decrypt_mpin(encrypted_mpin):
    """
    Decrypt MPIN. Tries, in order: ``MPIN_ENCRYPTION_KEY`` (if set), legacy ``SECRET_KEY`` hash,
    then ``ENCRYPTION_KEY`` hash (decrypt-only fallback for misconfigured environments).
    """
    from cryptography.fernet import Fernet

    last_err: Optional[Exception] = None
    for key in _mpin_decrypt_fernet_key_candidates():
        try:
            return Fernet(key).decrypt(encrypted_mpin.encode()).decode()
        except Exception as exc:
            last_err = exc
    if last_err:
        raise last_err
    raise ValueError('No MPIN decryption key candidates configured')


def _get_integration_encryption_key():
    """
    Build a stable Fernet key for integration secret storage.
    Prefers INTEGRATION_SECRET_KEY; falls back to SECRET_KEY-derived key.
    """
    from cryptography.fernet import Fernet
    import base64
    import hashlib

    raw = getattr(settings, 'INTEGRATION_SECRET_KEY', '') or settings.SECRET_KEY
    key_material = hashlib.sha256(str(raw).encode()).digest()
    return base64.urlsafe_b64encode(key_material)


def encrypt_secret_payload(payload):
    """Encrypt a dict payload for integration credentials at rest."""
    from cryptography.fernet import Fernet

    if payload is None:
        payload = {}
    data = json.dumps(payload, separators=(',', ':'))
    f = Fernet(_get_integration_encryption_key())
    return f.encrypt(data.encode()).decode()


def decrypt_secret_payload(encrypted_text):
    """Decrypt integration credentials payload; returns dict on failure-safe path."""
    from cryptography.fernet import Fernet, InvalidToken

    if not encrypted_text:
        return {}
    f = Fernet(_get_integration_encryption_key())
    try:
        raw = f.decrypt(str(encrypted_text).encode()).decode()
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError):
        return {}
