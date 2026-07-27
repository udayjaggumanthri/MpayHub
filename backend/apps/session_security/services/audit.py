"""Append-only login/session audit logger."""
from __future__ import annotations

import logging
from typing import Any

from apps.session_security.models import UserLoginAuditLog
from apps.session_security.services.settings import get_settings

logger = logging.getLogger(__name__)


class AuditLogger:
    def record(
        self,
        *,
        event_type: str,
        user=None,
        phone_attempted: str = '',
        ip_address: str | None = None,
        location: dict | None = None,
        user_agent: str = '',
        session=None,
        message: str = '',
        metadata: dict | None = None,
        force: bool = False,
    ) -> UserLoginAuditLog | None:
        try:
            if not force and not get_settings().audit_logging_enabled:
                return None
            return UserLoginAuditLog.objects.create(
                user=user,
                phone_attempted=(phone_attempted or '')[:20],
                event_type=event_type,
                ip_address=ip_address or None,
                location=location or {},
                user_agent=(user_agent or '')[:2000],
                session=session,
                message=(message or '')[:2000],
                metadata=metadata or {},
            )
        except Exception:  # noqa: BLE001 — never break auth on audit failure
            logger.exception('Failed to write session audit event %s', event_type)
            return None


def get_audit_logger() -> AuditLogger:
    return AuditLogger()
