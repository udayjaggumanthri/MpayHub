"""Fingpay onboarding master data (states, company types)."""
from __future__ import annotations

import logging

import requests
from django.core.cache import cache

from apps.integrations.fingpay.client import FingpayClientError
from apps.integrations.fingpay.registry import get_fingpay_client

logger = logging.getLogger(__name__)

CACHE_TTL = 60 * 60 * 6  # 6 hours

# Production edge sometimes returns 403 on unauthenticated GET masters while
# encrypted API POSTs work. UAT masters share the same stateId / companyType ids.
_FALLBACK_STATES_URL = 'https://fpuat.tapits.in/fpaepsweb/api/onboarding/getstates'
_FALLBACK_COMPANY_TYPES_URL = 'https://fpuat.tapits.in/fpaepsweb/api/onboarding/get/companyType/master'


def _http_get_json(url: str) -> object:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_states(*, force: bool = False) -> list[dict]:
    key = 'aeps:fingpay:states'
    if not force:
        cached = cache.get(key)
        if cached is not None:
            return cached
    rows = []
    try:
        client = get_fingpay_client()
        rows = client.get_onboarding_states()
    except FingpayClientError as exc:
        logger.warning('Fingpay states via provider failed: %s', exc)
    if not rows:
        try:
            data = _http_get_json(_FALLBACK_STATES_URL)
            rows = data if isinstance(data, list) else (data.get('data') or [])
            logger.warning('Loaded Fingpay states from UAT fallback (prod GET blocked/empty)')
        except Exception as exc:
            logger.warning('Fingpay states fallback failed: %s', exc)
            rows = []
    cleaned = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        sid = row.get('stateId') if row.get('stateId') is not None else row.get('id')
        name = row.get('state') or row.get('stateName') or ''
        if sid is None or not name:
            continue
        cleaned.append(
            {
                'stateId': int(sid),
                'state': str(name),
                'stateCode': str(row.get('stateCode') or ''),
            }
        )
    cleaned.sort(key=lambda x: x['state'].lower())
    if cleaned:
        cache.set(key, cleaned, CACHE_TTL)
    return cleaned


def fetch_company_types(*, force: bool = False) -> list[dict]:
    # v2: companyType on create must be mccCode (e.g. 4812), not master row id (e.g. 4).
    key = 'aeps:fingpay:company_types:v2'
    if not force:
        cached = cache.get(key)
        if cached is not None:
            return cached
    rows = []
    try:
        client = get_fingpay_client()
        rows = client.get_company_types()
    except FingpayClientError as exc:
        logger.warning('Fingpay company types via provider failed: %s', exc)
    if not rows:
        try:
            data = _http_get_json(_FALLBACK_COMPANY_TYPES_URL)
            rows = data if isinstance(data, list) else (data.get('data') or [])
            logger.warning('Loaded Fingpay company types from UAT fallback (prod GET blocked/empty)')
        except Exception as exc:
            logger.warning('Fingpay company types fallback failed: %s', exc)
            rows = []
    cleaned = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        cid = row.get('id')
        mcc = row.get('mccCode')
        if mcc is None:
            continue
        try:
            mcc_int = int(mcc)
        except (TypeError, ValueError):
            continue
        try:
            row_id = int(cid) if cid is not None else mcc_int
        except (TypeError, ValueError):
            row_id = mcc_int
        desc = str(row.get('mccDescription') or '').strip()
        cleaned.append(
            {
                'id': row_id,  # master row id — do NOT send as companyType
                'mccCode': mcc_int,
                # Value Fingpay validates on /simple/creation/v2 (see curl sample: 4812)
                'companyType': mcc_int,
                'mccDescription': desc,
                'label': f'{mcc_int} — {desc}',
            }
        )
    cleaned.sort(key=lambda x: (x.get('mccDescription') or '').lower())
    if cleaned:
        cache.set(key, cleaned, CACHE_TTL)
    return cleaned


def resolve_company_type(value, types: list[dict] | None = None) -> int | None:
    """
    Resolve companyType for Fingpay create.

    Fingpay expects MCC code (e.g. 4812), not the master list's sequential id (e.g. 4).
    Accepts mccCode directly, or a legacy draft that stored master id.
    """
    if value is None or value == '':
        return None
    rows = types if types is not None else fetch_company_types()
    try:
        num = int(value)
    except (TypeError, ValueError):
        return None
    mcc_set = {int(r['mccCode']) for r in rows if r.get('mccCode') is not None}
    if num in mcc_set:
        return num
    # Legacy UI saved master row id — map id → mccCode
    for row in rows:
        if int(row.get('id')) == num and row.get('mccCode') is not None:
            return int(row['mccCode'])
    return None


def resolve_state_id(value, states: list[dict] | None = None) -> int | None:
    """Accept stateId int/str or state name → Fingpay integer stateId."""
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    name = str(value).strip().lower()
    rows = states if states is not None else fetch_states()
    for row in rows:
        if row['state'].lower() == name or (row.get('stateCode') or '').lower() == name:
            return int(row['stateId'])
    # soft match
    for row in rows:
        if name in row['state'].lower() or row['state'].lower() in name:
            return int(row['stateId'])
    return None
