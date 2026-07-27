"""
Facade used by authentication views / JWT auth.

Keeps login/logout/refresh adapters thin while owning IP/geo + session policy.
"""
from __future__ import annotations

from typing import Any

from apps.session_security.constants import (
    EVENT_GEO_CAPTURE_FAILED,
    EVENT_LOGIN_FAILURE,
    EVENT_LOGIN_SUCCESS,
    EVENT_REFRESH_DENIED,
    SESSION_CLAIM,
)
from apps.session_security.exceptions import (
    GeoCaptureFailed,
    IpCaptureFailed,
    SessionIdleTimeout,
    SessionInvalid,
    SessionReplaced,
    SessionSecurityError,
)
from apps.session_security.services.audit import get_audit_logger
from apps.session_security.services.geo import get_geo_provider
from apps.session_security.services.ip import get_client_ip, get_user_agent
from apps.session_security.services.sessions import get_session_lifecycle
from apps.session_security.services.settings import get_settings


class SessionSecurityFacade:
    def capture_network(self, request, *, require: bool | None = None) -> tuple[str, dict]:
        settings_row = get_settings()
        if require is None:
            require = bool(settings_row.ip_location_enforcement_enabled)

        try:
            ip = get_client_ip(request)
        except IpCaptureFailed:
            if require:
                raise
            ip = (request.META.get('REMOTE_ADDR') or '0.0.0.0').strip() or '0.0.0.0'

        try:
            location = get_geo_provider().lookup(ip)
        except GeoCaptureFailed:
            if require:
                raise
            location = {
                'country': 'XX',
                'country_name': 'Unknown',
                'region': '',
                'city': 'Unknown',
                'latitude': None,
                'longitude': None,
                'source': 'unavailable',
                'ip': ip,
            }
        return ip, location

    def complete_login(
        self, request, user, *, client_context: dict | None = None
    ) -> tuple[dict[str, str], Any]:
        """
        Capture IP/geo (fail closed when enforced), create session + tokens.
        Optional client_context (browser geo + device) is sanitized and stored
        in audit metadata / session.device_info — never trusted for IP.
        Returns (tokens, session).
        """
        from apps.session_security.services.client_context import (
            build_login_audit_metadata,
            merge_session_device_info,
        )

        audit = get_audit_logger()
        ua = get_user_agent(request)
        settings_row = get_settings()

        try:
            ip, location = self.capture_network(request)
        except (IpCaptureFailed, GeoCaptureFailed) as exc:
            audit.record(
                event_type=EVENT_GEO_CAPTURE_FAILED,
                user=user,
                phone_attempted=getattr(user, 'phone', '') or '',
                user_agent=ua,
                message=str(exc),
                force=True,
                metadata=build_login_audit_metadata(
                    client_context=client_context,
                    ip_location=None,
                ),
            )
            raise

        device_info = merge_session_device_info(
            existing=None,
            ip_address=ip,
            location=location,
            user_agent=ua,
            client_context=client_context,
        )

        lifecycle = get_session_lifecycle()
        session, tokens = lifecycle.create_session(
            user=user,
            ip_address=ip,
            location=location,
            user_agent=ua,
            device_info=device_info,
        )
        audit.record(
            event_type=EVENT_LOGIN_SUCCESS,
            user=user,
            phone_attempted=getattr(user, 'phone', '') or '',
            ip_address=ip,
            location=location,
            user_agent=ua,
            session=session,
            message='Login successful',
            metadata=build_login_audit_metadata(
                client_context=client_context,
                ip_location=location,
                base={
                    'single_session': bool(settings_row.single_session_enforcement_enabled),
                    'allow_concurrent': bool(
                        getattr(user, 'allow_concurrent_sessions', False)
                    ),
                },
            ),
        )
        return tokens, session

    def record_login_failure(
        self,
        request,
        *,
        phone: str = '',
        message: str = '',
        user=None,
        client_context: dict | None = None,
    ):
        from apps.session_security.services.client_context import build_login_audit_metadata

        ua = get_user_agent(request)
        ip = None
        location = {}
        try:
            ip, location = self.capture_network(request, require=False)
        except SessionSecurityError:
            pass
        get_audit_logger().record(
            event_type=EVENT_LOGIN_FAILURE,
            user=user,
            phone_attempted=phone or '',
            ip_address=ip,
            location=location,
            user_agent=ua,
            message=message or 'Login failed',
            metadata=build_login_audit_metadata(
                client_context=client_context,
                ip_location=location,
            ),
        )

    def logout(self, request, user) -> None:
        ua = get_user_agent(request)
        ip, location = self.capture_network(request, require=False)
        sid = None
        auth = getattr(request, 'auth', None)
        if auth is not None and hasattr(auth, 'get'):
            sid = auth.get(SESSION_CLAIM)
        lifecycle = get_session_lifecycle()
        session = lifecycle.get_active_session_by_sid(sid)
        if session and session.user_id == user.id:
            lifecycle.logout_session(
                session,
                ip_address=ip,
                location=location,
                user_agent=ua,
            )

    def refresh(self, request, refresh_token_obj, user) -> dict[str, str]:
        """
        Validate session on refresh; re-capture IP/geo when enforcement is on.
        Returns token dict {access, refresh}.
        """
        audit = get_audit_logger()
        ua = get_user_agent(request)
        sid = refresh_token_obj.get(SESSION_CLAIM)
        lifecycle = get_session_lifecycle()
        settings_row = get_settings()

        try:
            ip, location = self.capture_network(request)
        except (IpCaptureFailed, GeoCaptureFailed) as exc:
            audit.record(
                event_type=EVENT_GEO_CAPTURE_FAILED,
                user=user,
                phone_attempted=getattr(user, 'phone', '') or '',
                user_agent=ua,
                message=str(exc),
                force=True,
            )
            audit.record(
                event_type=EVENT_REFRESH_DENIED,
                user=user,
                phone_attempted=getattr(user, 'phone', '') or '',
                user_agent=ua,
                message=str(exc),
            )
            raise

        try:
            session = lifecycle.validate_session(
                sid,
                user=user,
                touch=True,
                ip_address=ip,
                location=location,
                user_agent=ua,
            )
        except (SessionInvalid, SessionReplaced, SessionIdleTimeout) as exc:
            audit.record(
                event_type=EVENT_REFRESH_DENIED,
                user=user,
                phone_attempted=getattr(user, 'phone', '') or '',
                ip_address=ip,
                location=location,
                user_agent=ua,
                message=str(exc),
            )
            raise

        if settings_row.ip_location_enforcement_enabled:
            lifecycle.update_session_network(
                session,
                ip_address=ip,
                location=location,
                user_agent=ua,
            )

        from apps.session_security.services.sessions import attach_sid_to_access

        access = attach_sid_to_access(refresh_token_obj, session.jti)
        return {
            'access': access,
            'refresh': str(refresh_token_obj),
        }

    def authenticate_access(self, request, validated_token, user):
        """Validate sid session for JWT access tokens; touch activity."""
        sid = None
        try:
            sid = validated_token.get(SESSION_CLAIM)
        except Exception:  # noqa: BLE001
            sid = None
        ua = get_user_agent(request)
        # Do not require geo on every API call — only idle/active checks.
        ip = None
        try:
            ip = get_client_ip(request)
        except IpCaptureFailed:
            ip = None
        return get_session_lifecycle().validate_session(
            sid,
            user=user,
            touch=True,
            ip_address=ip,
            user_agent=ua,
        )


def get_facade() -> SessionSecurityFacade:
    return SessionSecurityFacade()
