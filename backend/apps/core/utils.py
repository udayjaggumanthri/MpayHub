"""
Utility functions for the mPayhub platform.
"""
import random
import string
from datetime import datetime
import json
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


def _get_encryption_key():
    """
    Get consistent encryption key from SECRET_KEY.
    This ensures the same key is used for encryption and decryption.
    """
    from cryptography.fernet import Fernet
    from django.conf import settings
    import base64
    import hashlib
    
    # Generate a consistent key from SECRET_KEY
    # Use SHA256 hash of SECRET_KEY and encode to base64
    secret_key = settings.SECRET_KEY.encode()
    key_material = hashlib.sha256(secret_key).digest()
    key = base64.urlsafe_b64encode(key_material)
    return key


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
    Decrypt MPIN using the same key used for encryption.
    """
    from cryptography.fernet import Fernet
    
    key = _get_encryption_key()
    f = Fernet(key)
    decrypted = f.decrypt(encrypted_mpin.encode())
    return decrypted.decode()


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
