"""
Normalize optional client_context from login payloads.

Trust boundary: never trust client-claimed IP. Server owns IP + IP GeoIP.
Browser coords and device facts are advisory for audit / fraud monitoring.
"""
from __future__ import annotations

from typing import Any


def _clamp_str(value: Any, max_len: int) -> str:
    if value is None:
        return ''
    return str(value).strip()[:max_len]


def _as_float(value: Any) -> float | None:
    if value is None or value == '':
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:  # NaN
        return None
    return num


def normalize_browser_geo(raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    status = _clamp_str(data.get('status'), 32).lower() or 'unavailable'
    if status not in ('granted', 'denied', 'unavailable', 'timeout', 'pending'):
        status = 'unavailable'

    lat = _as_float(data.get('latitude'))
    lng = _as_float(data.get('longitude'))
    accuracy = _as_float(data.get('accuracy'))

    if status == 'granted':
        if lat is None or lng is None or lat < -90 or lat > 90 or lng < -180 or lng > 180:
            status = 'unavailable'
            lat = None
            lng = None
            accuracy = None
        elif accuracy is not None and (accuracy < 0 or accuracy > 100_000):
            accuracy = None
    else:
        # Do not store coords unless granted
        lat = None
        lng = None
        accuracy = None

    return {
        'status': status,
        'latitude': lat,
        'longitude': lng,
        'accuracy': accuracy,
        'source': 'browser',
    }


def normalize_device(raw: Any) -> dict[str, str]:
    data = raw if isinstance(raw, dict) else {}
    device_type = _clamp_str(data.get('device_type'), 32).lower() or 'desktop'
    if device_type not in ('desktop', 'mobile', 'tablet'):
        device_type = 'desktop'
    return {
        'browser_name': _clamp_str(data.get('browser_name'), 64) or 'Unknown',
        'browser_version': _clamp_str(data.get('browser_version'), 32),
        'os': _clamp_str(data.get('os'), 64) or 'Unknown',
        'device_type': device_type,
        'screen': _clamp_str(data.get('screen'), 32),
        'timezone': _clamp_str(data.get('timezone'), 64),
        'language': _clamp_str(data.get('language'), 32),
        'user_agent': _clamp_str(data.get('user_agent'), 2000),
    }


def location_resolution_for(browser_geo: dict[str, Any], *, has_ip_location: bool) -> str:
    if browser_geo.get('status') == 'granted' and browser_geo.get('latitude') is not None:
        return 'browser'
    if has_ip_location:
        return 'ip_fallback'
    return 'unavailable'


def normalize_client_context(raw: Any) -> dict[str, Any]:
    """
    Return a sanitized client_context dict, or empty dict if unusable.
    Never raises.
    """
    if not isinstance(raw, dict) or not raw:
        return {}
    try:
        browser_geo = normalize_browser_geo(raw.get('browser_geo'))
        device = normalize_device(raw.get('device'))
        captured_at = _clamp_str(raw.get('captured_at'), 64)
        return {
            'browser_geo': browser_geo,
            'device': device,
            'captured_at': captured_at,
        }
    except Exception:  # noqa: BLE001
        return {}


def build_login_audit_metadata(
    *,
    client_context: dict[str, Any] | None,
    ip_location: dict | None,
    base: dict | None = None,
) -> dict[str, Any]:
    """Merge session flags + normalized client context for UserLoginAuditLog.metadata."""
    meta = dict(base or {})
    ctx = normalize_client_context(client_context)
    if not ctx:
        # Still mark resolution from IP alone when no client bag
        has_ip = bool(
            isinstance(ip_location, dict)
            and (ip_location.get('city') or ip_location.get('country'))
        )
        meta.setdefault(
            'location_resolution',
            'ip_fallback' if has_ip else 'unavailable',
        )
        return meta

    browser_geo = ctx['browser_geo']
    device = ctx['device']
    has_ip = bool(
        isinstance(ip_location, dict)
        and (ip_location.get('city') or ip_location.get('country'))
        and (ip_location.get('source') not in ('unavailable', 'none', ''))
    )
    meta['browser_geo'] = browser_geo
    meta['device'] = device
    meta['location_resolution'] = location_resolution_for(
        browser_geo, has_ip_location=has_ip
    )
    if ctx.get('captured_at'):
        meta['client_captured_at'] = ctx['captured_at']
    return meta


def merge_session_device_info(
    *,
    existing: dict | None,
    ip_address: str | None,
    location: dict | None,
    user_agent: str,
    client_context: dict | None,
) -> dict[str, Any]:
    device = dict(existing or {})
    device['ip'] = ip_address
    device['location'] = location or {}
    device['user_agent'] = (user_agent or '')[:500]
    ctx = normalize_client_context(client_context)
    if ctx.get('browser_geo'):
        device['browser_geo'] = ctx['browser_geo']
    if ctx.get('device'):
        device['client_device'] = ctx['device']
    if ctx.get('captured_at'):
        device['client_captured_at'] = ctx['captured_at']
    return device
