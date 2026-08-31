"""
Outbound IP discovery for Fingpay allowlists.

Fingpay's onboarding payload carries `ipAddress`, and Tapits' allowlist is keyed
on the address we actually egress from. Hardcoding that address means it silently
goes stale whenever the host moves, so it is detected at runtime and the stored
provider config is only a fallback for when detection is unavailable.
"""
from __future__ import annotations

import ipaddress
import socket
import threading
import time
from urllib.parse import urlparse

# Detection is a routing-table lookup, but it is on the request path, so keep a
# short process-local cache rather than repeating it per call.
_CACHE_TTL_SECONDS = 300
_lock = threading.Lock()
_cache: dict[str, tuple[str, float]] = {}


def detect_outbound_ipv4(*, hostname: str = '', port: int = 443) -> str:
    """
    Return this host's source IPv4 for traffic to `hostname`, or '' if unknown.

    Uses a UDP connect, which only asks the kernel to pick a route — no packets
    are sent and the peer is never contacted.
    """
    target = (hostname or '').strip() or '1.1.1.1'
    now = time.monotonic()
    with _lock:
        hit = _cache.get(target)
        if hit and now - hit[1] < _CACHE_TTL_SECONDS:
            return hit[0]

    ip = ''
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect((target, port))
            ip = (sock.getsockname()[0] or '').strip()
        finally:
            sock.close()
    except OSError:
        ip = ''

    # Behind NAT the kernel reports a private source address, which is never the
    # address Tapits sees. Treat that as "unknown" so the configured override wins.
    if not _is_public_ipv4(ip):
        ip = ''

    if ip:
        with _lock:
            _cache[target] = (ip, now)
    return ip


def _is_public_ipv4(ip: str) -> bool:
    try:
        addr = ipaddress.IPv4Address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_unspecified
    )


def hostname_from_url(url: str) -> str:
    try:
        return urlparse(url or '').hostname or ''
    except ValueError:
        return ''


def resolve_egress_ip(configured: str = '', *, url: str = '', hostname: str = '') -> str:
    """
    The address Tapits will see us from.

    Detection wins when it yields a public address, because a stored value goes
    stale the moment the host moves. The configured value is the override for
    NAT deployments, where the kernel only knows a private source address.
    """
    detected = detect_outbound_ipv4(hostname=hostname or hostname_from_url(url))
    return detected or (configured or '').strip()


def clear_cache() -> None:
    with _lock:
        _cache.clear()
