"""Bind client IP / UA into ContextVar for activity audit during the request."""
from __future__ import annotations

import logging

from apps.session_security.exceptions import IpCaptureFailed
from apps.session_security.services.ip import get_client_ip, get_user_agent
from apps.session_security.services.request_context import (
    clear_request_network,
    set_request_network,
)

logger = logging.getLogger(__name__)


class SessionSecurityRequestContextMiddleware:
    """
    Lightweight: capture IP + UA only (no GeoIP on every request).
    Geo is resolved lazily when money/admin activity is recorded.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = None
        try:
            ip = get_client_ip(request)
        except IpCaptureFailed:
            remote = (request.META.get('REMOTE_ADDR') or '').strip() or None
            ip = remote
        except Exception:  # noqa: BLE001
            logger.debug('Failed to resolve client IP for audit context', exc_info=True)
            ip = None

        set_request_network(ip_address=ip, user_agent=get_user_agent(request))
        try:
            return self.get_response(request)
        finally:
            clear_request_network()
