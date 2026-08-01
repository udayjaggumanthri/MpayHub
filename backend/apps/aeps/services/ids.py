"""Helpers for AEPS merchant txn ids and pin decryption."""
from __future__ import annotations

import secrets
import string
from datetime import datetime

from apps.core.utils import decrypt_secret_payload


def generate_merchant_tran_id(prefix: str = 'AE') -> str:
    stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    rand = ''.join(secrets.choice(string.digits) for _ in range(6))
    return f'{prefix}{stamp}{rand}'[:64]


def merchant_pin_plain(merchant) -> str:
    data = decrypt_secret_payload(merchant.merchant_pin_encrypted or '') or {}
    return str(data.get('pin') or '')
