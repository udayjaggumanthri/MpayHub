"""
Resolve VimoPay beneficiaryLocation (state code) from a saved bank account.

Primary sources:
1. verification_details / ifsc_details captured at bank validation
2. Public IFSC directory lookup (Razorpay IFSC API) using bank IFSC
3. Optional client-provided preferred location (backward compatible)
"""
from __future__ import annotations

import logging
from typing import Any

import requests
from django.core.cache import cache

from apps.integrations.payout.masters_cache import match_state_code
from apps.integrations.payout.types import MasterItem

logger = logging.getLogger(__name__)

_IFSC_CACHE_PREFIX = 'payout_ifsc_state'
_IFSC_CACHE_TTL = 7 * 24 * 60 * 60  # 7 days
_IFSC_LOOKUP_TIMEOUT = 4


def _pick_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ''


def _hints_from_verification_details(details: dict) -> list[str]:
    hints: list[str] = []
    if not isinstance(details, dict):
        return hints

    for key in ('state', 'State', 'STATE', 'beneficiary_state', 'location'):
        text = _pick_text(details.get(key))
        if text:
            hints.append(text)

    ifsc_details = details.get('ifsc_details')
    if isinstance(ifsc_details, dict):
        for key in ('state', 'State', 'STATE', 'iso3166', 'ISO3166'):
            text = _pick_text(ifsc_details.get(key))
            if text:
                hints.append(text)

    return hints


def lookup_ifsc_state(ifsc: str) -> str:
    """
    Return state name for an IFSC (e.g. ANDHRA PRADESH), or '' on failure.
    Uses Razorpay's public IFSC directory; results are cached.
    """
    code = (ifsc or '').strip().upper()
    if len(code) != 11:
        return ''

    cache_key = f'{_IFSC_CACHE_PREFIX}:{code}'
    cached = cache.get(cache_key)
    if isinstance(cached, str):
        return cached

    state = ''
    try:
        resp = requests.get(
            f'https://ifsc.razorpay.com/{code}',
            timeout=_IFSC_LOOKUP_TIMEOUT,
        )
        if resp.status_code == 200:
            payload = resp.json() if resp.content else {}
            if isinstance(payload, dict):
                state = _pick_text(payload.get('STATE'), payload.get('state'))
    except Exception:
        logger.warning('IFSC state lookup failed for %s', code, exc_info=True)

    cache.set(cache_key, state, timeout=_IFSC_CACHE_TTL)
    return state


def resolve_beneficiary_location(
    *,
    bank_account,
    states: list[MasterItem],
    preferred: str = '',
) -> str | None:
    """
    Resolve a provider master state code for payout beneficiaryLocation.

    Prefer bank-account derived location; fall back to a valid preferred code/name.
    """
    if not states:
        return None

    hints: list[str] = []
    details = getattr(bank_account, 'verification_details', None) or {}
    hints.extend(_hints_from_verification_details(details if isinstance(details, dict) else {}))

    ifsc = _pick_text(getattr(bank_account, 'ifsc', ''))
    ifsc_state = lookup_ifsc_state(ifsc) if ifsc else ''
    if ifsc_state:
        hints.append(ifsc_state)

    # City is a weak signal; try only after stronger hints fail.
    city = _pick_text(getattr(bank_account, 'city', ''), (details or {}).get('city') if isinstance(details, dict) else '')

    for hint in hints:
        matched = match_state_code(states, hint)
        if matched:
            return matched

    if city:
        matched = match_state_code(states, city)
        if matched:
            return matched

    preferred_text = (preferred or '').strip()
    if preferred_text:
        matched = match_state_code(states, preferred_text)
        if matched:
            return matched

    return None
