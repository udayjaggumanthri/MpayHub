"""Client IP resolution (proxy-aware, spoof-resistant behind nginx)."""
from __future__ import annotations

import ipaddress

from django.conf import settings

from apps.session_security.exceptions import IpCaptureFailed


def _is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _is_internal_proxy_hop(value: str) -> bool:
    """
    True for hops that are not a public client address.

    Uses RFC1918 / loopback / link-local / CGNAT only — not Python's
    broader ``is_private`` (which also flags TEST-NET documentation ranges).
    """
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return True
    if addr.is_loopback or addr.is_link_local or addr.is_multicast:
        return True
    if isinstance(addr, ipaddress.IPv4Address):
        return any(
            addr in net
            for net in (
                ipaddress.ip_network('10.0.0.0/8'),
                ipaddress.ip_network('172.16.0.0/12'),
                ipaddress.ip_network('192.168.0.0/16'),
                ipaddress.ip_network('100.64.0.0/10'),
            )
        )
    if isinstance(addr, ipaddress.IPv6Address):
        return addr.ipv4_mapped is not None and _is_internal_proxy_hop(
            str(addr.ipv4_mapped)
        ) or addr in ipaddress.ip_network('fc00::/7')
    return False


def _xff_candidates(xff: str) -> list[str]:
    out: list[str] = []
    for part in xff.split(','):
        candidate = part.strip()
        if candidate and _is_valid_ip(candidate):
            out.append(candidate)
    return out


def _pick_from_xff(candidates: list[str]) -> str | None:
    """
    Prefer the rightmost public IP (the hop our reverse proxy appends).

    Client-supplied left-most XFF values are spoofable; nginx's
    `$proxy_add_x_forwarded_for` appends the real connecting peer last.
    """
    if not candidates:
        return None
    for candidate in reversed(candidates):
        if not _is_internal_proxy_hop(candidate):
            return candidate
    # All internal (e.g. mesh) — use rightmost valid hop
    return candidates[-1]


class ClientIpResolver:
    """
    Resolve client IP from request.

    When TRUST_X_FORWARDED_FOR is True (typical behind nginx):
      1. X-Real-IP (nginx sets to $remote_addr — not client-spoofable)
      2. Rightmost public entry in X-Forwarded-For
      3. REMOTE_ADDR

    When trust is False, only REMOTE_ADDR is used.
    """

    def resolve(self, request) -> str:
        trust_proxy = bool(getattr(settings, 'TRUST_X_FORWARDED_FOR', True))
        if trust_proxy:
            xri = (request.META.get('HTTP_X_REAL_IP') or '').strip()
            if xri and _is_valid_ip(xri):
                return xri

            xff = (request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
            if xff:
                picked = _pick_from_xff(_xff_candidates(xff))
                if picked:
                    return picked

        remote = (request.META.get('REMOTE_ADDR') or '').strip()
        if remote and _is_valid_ip(remote):
            return remote

        raise IpCaptureFailed('Unable to determine client IP address.')


def get_client_ip(request) -> str:
    return ClientIpResolver().resolve(request)


def get_user_agent(request) -> str:
    return (request.META.get('HTTP_USER_AGENT') or '')[:2000]
