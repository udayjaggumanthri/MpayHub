"""Best-effort device summary from User-Agent (no third-party SDK)."""
from __future__ import annotations

import re
from typing import Any


def parse_browser(ua: str) -> tuple[str, str]:
    s = ua or ''
    rules = [
        ('Edge', r'Edg(?:e|A|iOS)?/([\d.]+)'),
        ('Opera', r'OPR/([\d.]+)'),
        ('Chrome', r'Chrome/([\d.]+)'),
        ('Firefox', r'Firefox/([\d.]+)'),
        ('Safari', r'Version/([\d.]+).*Safari'),
        ('Samsung Internet', r'SamsungBrowser/([\d.]+)'),
    ]
    for name, pattern in rules:
        m = re.search(pattern, s)
        if m:
            ver = (m.group(1) or '').split('.')[0]
            return name, ver
    return 'Unknown', ''


def parse_os(ua: str) -> str:
    s = ua or ''
    if re.search(r'Windows NT 10', s, re.I):
        return 'Windows'
    if re.search(r'Windows', s, re.I):
        return 'Windows'
    if re.search(r'Android', s, re.I):
        return 'Android'
    if re.search(r'iPhone|iPad|iPod', s, re.I):
        return 'iOS'
    if re.search(r'Mac OS X', s, re.I):
        return 'macOS'
    if re.search(r'CrOS', s, re.I):
        return 'Chrome OS'
    if re.search(r'Linux', s, re.I):
        return 'Linux'
    return 'Unknown'


def parse_device_type(ua: str) -> str:
    s = ua or ''
    if re.search(r'iPad|Tablet|PlayBook', s, re.I) or (
        re.search(r'Android', s, re.I) and not re.search(r'Mobile', s, re.I)
    ):
        return 'tablet'
    if re.search(r'Mobi|iPhone|iPod|Android.*Mobile|webOS|BlackBerry|IEMobile', s, re.I):
        return 'mobile'
    return 'desktop'


def device_from_user_agent(ua: str) -> dict[str, str]:
    ua = (ua or '')[:2000]
    browser_name, browser_version = parse_browser(ua)
    return {
        'browser_name': browser_name,
        'browser_version': browser_version,
        'os': parse_os(ua),
        'device_type': parse_device_type(ua),
        'screen': '',
        'timezone': '',
        'language': '',
        'user_agent': ua,
    }


def device_from_session_info(device_info: dict | None) -> dict[str, Any]:
    info = device_info if isinstance(device_info, dict) else {}
    client = info.get('client_device') if isinstance(info.get('client_device'), dict) else {}
    if client.get('browser_name') or client.get('os'):
        return {
            'browser_name': str(client.get('browser_name') or 'Unknown'),
            'browser_version': str(client.get('browser_version') or ''),
            'os': str(client.get('os') or 'Unknown'),
            'device_type': str(client.get('device_type') or 'desktop'),
            'screen': str(client.get('screen') or ''),
            'timezone': str(client.get('timezone') or ''),
            'language': str(client.get('language') or ''),
            'user_agent': str(client.get('user_agent') or info.get('user_agent') or '')[:2000],
        }
    return {}
