"""
Cache bank / state / purpose master lists per provider to avoid hammering VimoPay.
"""
from __future__ import annotations

import logging
import time
from typing import Literal

from django.core.cache import cache

from apps.integrations.payout.port import PayoutProvider
from apps.integrations.payout.types import MasterItem

logger = logging.getLogger(__name__)

MasterKind = Literal['banks', 'states', 'purposes']

_CACHE_PREFIX = 'payout_master'
_DEFAULT_TTL = 6 * 60 * 60  # 6 hours


def _cache_key(provider_code: str, kind: MasterKind) -> str:
    return f'{_CACHE_PREFIX}:{provider_code}:{kind}'


def _ttl_from_provider(provider: PayoutProvider) -> int:
    cfg = getattr(getattr(provider, 'master', None), 'config_json', None) or {}
    if isinstance(cfg, dict):
        try:
            return max(300, min(int(cfg.get('masters_ttl_seconds') or _DEFAULT_TTL), 86400))
        except (TypeError, ValueError):
            pass
    return _DEFAULT_TTL


def _fetch(provider: PayoutProvider, kind: MasterKind) -> list[MasterItem]:
    if kind == 'banks':
        return provider.list_banks()
    if kind == 'states':
        return provider.list_states()
    return provider.list_purposes()


def get_masters(
    provider: PayoutProvider,
    kind: MasterKind,
    *,
    force_refresh: bool = False,
) -> list[MasterItem]:
    key = _cache_key(provider.provider_code, kind)
    if not force_refresh:
        cached = cache.get(key)
        if isinstance(cached, list) and cached:
            return [MasterItem(code=r['code'], description=r['description']) for r in cached]

    items = _fetch(provider, kind)
    serializable = [{'code': i.code, 'description': i.description} for i in items]
    cache.set(key, serializable, timeout=_ttl_from_provider(provider))
    return items


def invalidate_masters(provider_code: str) -> None:
    for kind in ('banks', 'states', 'purposes'):
        cache.delete(_cache_key(provider_code, kind))


def match_bank_code(
    banks: list[MasterItem],
    *,
    bank_name: str = '',
    ifsc: str = '',
) -> str | None:
    """
    Map our BankAccount.bank_name / IFSC to a provider master bank code.
    Prefer exact (case-insensitive) name match, then substring, then IFSC bank prefix heuristics.
    Provider-agnostic — works for any master list shaped as MasterItem(code, description).
    """
    name = (bank_name or '').strip().lower()
    ifsc_u = (ifsc or '').strip().upper()
    if not banks:
        return None

    # Exact description match
    if name:
        for b in banks:
            if b.description.strip().lower() == name:
                return b.code
        # Substring either way
        for b in banks:
            desc = b.description.strip().lower()
            if name in desc or desc in name:
                return b.code
        # Common synonyms
        synonyms = {
            'hdfc': 'hdfc',
            'icici': 'icici',
            'axis': 'axis',
            'sbi': 'state bank',
            'state bank of india': 'state bank',
            'kotak': 'kotak',
            'yes bank': 'yes',
            'pnb': 'punjab national',
            'punjab national bank': 'punjab national',
            'bank of baroda': 'baroda',
            'canara': 'canara',
            'union bank': 'union',
            'idfc': 'idfc',
            'indusind': 'indusind',
            'federal': 'federal',
        }
        needle = synonyms.get(name)
        if needle:
            for b in banks:
                if needle in b.description.strip().lower():
                    return b.code

    # IFSC first 4 letters often identify the bank
    if len(ifsc_u) >= 4:
        prefix = ifsc_u[:4]
        ifsc_map = {
            'HDFC': 'hdfc',
            'ICIC': 'icici',
            'UTIB': 'axis',
            'SBIN': 'state bank of india',  # prefer SBI India over other "State Bank of *"
            'KKBK': 'kotak',
            'YESB': 'yes',
            'PUNB': 'punjab national',
            'BARB': 'baroda',
            'CNRB': 'canara',
            'UBIN': 'union',
            'IDFB': 'idfc',
            'INDB': 'indusind',
            'FDRL': 'federal',
            'IDIB': 'indian bank',
            'IOBA': 'indian overseas',
            'BKID': 'bank of india',
        }
        hint = ifsc_map.get(prefix)
        if hint:
            # Prefer exact / full-name match first
            for b in banks:
                if b.description.strip().lower() == hint:
                    return b.code
            for b in banks:
                if hint in b.description.strip().lower():
                    return b.code
            # SBIN fallback: any description that is exactly State Bank of India variants
            if prefix == 'SBIN':
                for b in banks:
                    d = b.description.strip().lower()
                    if d in ('state bank of india', 'sbi') or d.startswith('state bank of india'):
                        return b.code

    return None


def _norm_state_text(value: str) -> str:
    text = (value or '').strip().lower()
    for ch in ('&', ',', '.', '-', '_', '/', '(', ')'):
        text = text.replace(ch, ' ')
    text = ' '.join(text.split())
    # Common IFSC directory phrasing → master list names
    aliases = {
        'nct of delhi': 'delhi',
        'delhi ncr': 'delhi',
        'orissa': 'odisha',
        'pondicherry': 'puducherry',
        'uttaranchal': 'uttarakhand',
        'dadra and nagar haveli and daman and diu': 'dadra and nagar haveli',
        'andaman and nicobar': 'andaman and nicobar islands',
        'jammu & kashmir': 'jammu and kashmir',
    }
    return aliases.get(text, text)


def match_state_code(states: list[MasterItem], hint: str) -> str | None:
    """
    Map a free-text state (name, code, or ISO like IN-AP) to a provider master state code.
    """
    raw = (hint or '').strip()
    if not raw or not states:
        return None

    upper = raw.upper()
    if upper.startswith('IN-') and len(upper) >= 5:
        upper = upper[3:]
        raw = upper

    # Exact code match (e.g. AP, JH, MH)
    for item in states:
        code = (item.code or '').strip()
        if code and code.upper() == upper:
            return code

    needle = _norm_state_text(raw)
    if not needle:
        return None

    # Exact description match
    for item in states:
        desc = _norm_state_text(item.description or '')
        if desc and desc == needle:
            return (item.code or '').strip() or None

    # Prefix / containment (Andhra / Andhra Pradesh)
    for item in states:
        desc = _norm_state_text(item.description or '')
        if not desc:
            continue
        if needle in desc or desc in needle:
            return (item.code or '').strip() or None

    return None
