import re
from typing import Optional, Tuple


def normalize_phone(phone: str, country_code: str = '91') -> Tuple[Optional[str], str]:
    """
    Normalize to E.164 without plus: 91 + 10-digit Indian mobile.
    Returns (normalized, skip_reason). normalized is None when invalid.
    """
    digits = re.sub(r'\D', '', str(phone or ''))
    cc = re.sub(r'\D', '', str(country_code or '91')) or '91'

    if len(digits) == 10:
        return f'{cc}{digits}', ''
    if len(digits) == 12 and digits.startswith(cc):
        return digits, ''
    if len(digits) == 11 and digits.startswith('0'):
        return f'{cc}{digits[1:]}', ''
    return None, 'invalid_phone'


def mask_phone(phone_e164: str) -> str:
    digits = re.sub(r'\D', '', phone_e164 or '')
    if len(digits) < 4:
        return '****'
    return f'{"*" * max(0, len(digits) - 4)}{digits[-4:]}'
