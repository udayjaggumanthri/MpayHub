"""
Per-request network context for activity audit (thread/async-safe via ContextVar).

Money/admin signals often have no HttpRequest; middleware stores IP/UA so
passbook and admin activity can attach the same network facts as auth events.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger(__name__)

_network_ctx: ContextVar[dict[str, Any] | None] = ContextVar(
    'session_security_network', default=None
)


def set_request_network(
    *,
    ip_address: str | None = None,
    user_agent: str = '',
    location: dict | None = None,
) -> None:
    _network_ctx.set(
        {
            'ip_address': ip_address,
            'user_agent': (user_agent or '')[:2000],
            'location': location if isinstance(location, dict) else {},
        }
    )


def clear_request_network() -> None:
    _network_ctx.set(None)


def get_request_network(*, resolve_geo: bool = False) -> dict[str, Any]:
    """
    Return current request network snapshot.

    When resolve_geo=True and IP is known but location empty, perform a soft
    GeoIP lookup (cached). Never raises.
    """
    ctx = dict(_network_ctx.get() or {})
    if not resolve_geo:
        return ctx

    ip = ctx.get('ip_address')
    loc = ctx.get('location') if isinstance(ctx.get('location'), dict) else {}
    if ip and not (
        (loc.get('city') or loc.get('country') or loc.get('source'))
    ):
        try:
            from apps.session_security.services.geo import soft_lookup_location

            loc = soft_lookup_location(ip)
            ctx['location'] = loc
            _network_ctx.set(ctx)
        except Exception:  # noqa: BLE001
            logger.debug('request geo resolve failed for %s', ip, exc_info=True)
    return ctx
