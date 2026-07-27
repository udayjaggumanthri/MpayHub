"""User session lifecycle: create, replace, terminate, touch, validate."""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.settings import api_settings as jwt_api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authentication.models import UserSession
from apps.session_security.constants import (
    ACTIVITY_TOUCH_THROTTLE_SECONDS,
    EVENT_IDLE_TIMEOUT,
    EVENT_SESSION_REPLACED,
    SESSION_CLAIM,
    TERMINATION_ADMIN,
    TERMINATION_IDLE,
    TERMINATION_LOGOUT,
    TERMINATION_REPLACED,
)
from apps.session_security.exceptions import (
    SessionIdleTimeout,
    SessionInvalid,
    SessionReplaced,
)
from apps.session_security.services.audit import get_audit_logger
from apps.session_security.services.settings import get_settings


def _refresh_lifetime() -> timedelta:
    return jwt_api_settings.REFRESH_TOKEN_LIFETIME


def issue_tokens_for_session(user, session_id: str) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    refresh[SESSION_CLAIM] = session_id
    access = refresh.access_token
    access[SESSION_CLAIM] = session_id
    return {
        'access': str(access),
        'refresh': str(refresh),
    }


def attach_sid_to_access(refresh: RefreshToken, session_id: str) -> str:
    access = refresh.access_token
    access[SESSION_CLAIM] = session_id
    return str(access)


class SessionLifecycleService:
    def terminate_session(
        self,
        session: UserSession,
        *,
        reason: str,
        audit_user=None,
        ip_address: str | None = None,
        location: dict | None = None,
        user_agent: str = '',
        message: str = '',
    ) -> None:
        if not session.is_active:
            return
        now = timezone.now()
        session.is_active = False
        session.terminated_at = now
        session.termination_reason = reason
        session.save(
            update_fields=['is_active', 'terminated_at', 'termination_reason', 'updated_at']
        )

    def deactivate_other_sessions(
        self,
        user,
        *,
        keep_session_id: str | None = None,
        ip_address: str | None = None,
        location: dict | None = None,
        user_agent: str = '',
    ) -> int:
        qs = UserSession.objects.filter(user=user, is_active=True)
        if keep_session_id:
            qs = qs.exclude(jti=keep_session_id)
        sessions = list(qs)
        audit = get_audit_logger()
        for session in sessions:
            self.terminate_session(session, reason=TERMINATION_REPLACED)
            audit.record(
                event_type=EVENT_SESSION_REPLACED,
                user=user,
                phone_attempted=getattr(user, 'phone', '') or '',
                ip_address=ip_address,
                location=location,
                user_agent=user_agent,
                session=session,
                message='Previous session terminated due to new login.',
                metadata={'replaced_by_session_id': keep_session_id},
            )
        return len(sessions)

    @transaction.atomic
    def create_session(
        self,
        *,
        user,
        ip_address: str,
        location: dict,
        user_agent: str = '',
        enforce_single_session: bool | None = None,
        device_info: dict | None = None,
    ) -> tuple[UserSession, dict[str, str]]:
        settings_row = get_settings()
        if enforce_single_session is None:
            enforce_single_session = bool(settings_row.single_session_enforcement_enabled)

        session_id = str(uuid.uuid4())
        now = timezone.now()

        if enforce_single_session and not getattr(user, 'allow_concurrent_sessions', False):
            self.deactivate_other_sessions(
                user,
                keep_session_id=session_id,
                ip_address=ip_address,
                location=location,
                user_agent=user_agent,
            )

        tokens = issue_tokens_for_session(user, session_id)
        info = device_info if isinstance(device_info, dict) and device_info else {
            'ip': ip_address,
            'location': location or {},
            'user_agent': (user_agent or '')[:500],
        }
        session = UserSession.objects.create(
            user=user,
            token=session_id[:255],
            jti=session_id,
            ip_address=ip_address,
            location=location or {},
            user_agent=(user_agent or '')[:2000],
            device_info=info,
            expires_at=now + _refresh_lifetime(),
            is_active=True,
            last_activity_at=now,
        )
        return session, tokens

    def get_active_session_by_sid(self, session_id: str | None) -> UserSession | None:
        if not session_id:
            return None
        return (
            UserSession.objects.select_related('user')
            .filter(jti=session_id, is_active=True)
            .first()
        )

    def _idle_expired(self, session: UserSession, settings_row) -> bool:
        minutes = int(settings_row.idle_timeout_minutes or 0)
        if minutes <= 0:
            return False
        last = session.last_activity_at or session.created_at
        if not last:
            return False
        return timezone.now() > last + timedelta(minutes=minutes)

    def validate_session(
        self,
        session_id: str | None,
        *,
        user=None,
        touch: bool = True,
        ip_address: str | None = None,
        location: dict | None = None,
        user_agent: str = '',
    ) -> UserSession:
        settings_row = get_settings()
        session = self.get_active_session_by_sid(session_id)
        if session is None:
            # Distinguish replaced vs never existed when possible
            prior = None
            if session_id:
                prior = (
                    UserSession.objects.filter(jti=session_id)
                    .order_by('-created_at')
                    .first()
                )
            if prior and prior.termination_reason == TERMINATION_REPLACED:
                raise SessionReplaced(
                    'Your session was ended because you signed in on another device.'
                )
            if prior and prior.termination_reason == TERMINATION_IDLE:
                raise SessionIdleTimeout('Your session expired due to inactivity.')
            raise SessionInvalid('Session is invalid or has expired.')

        if user is not None and session.user_id != user.id:
            raise SessionInvalid('Session does not match authenticated user.')

        if not session.is_valid():
            self.terminate_session(session, reason=TERMINATION_LOGOUT)
            raise SessionInvalid('Session has expired.')

        if self._idle_expired(session, settings_row):
            self.terminate_session(session, reason=TERMINATION_IDLE)
            from apps.session_security.services.geo import coalesce_audit_network

            audit_ip, audit_location = coalesce_audit_network(
                ip_address=ip_address,
                location=location,
                fallback_ip=session.ip_address,
                fallback_location=session.location
                if isinstance(session.location, dict)
                else {},
            )
            idle_meta = {}
            try:
                from apps.session_security.services.device_parse import (
                    device_from_session_info,
                    device_from_user_agent,
                )

                device = device_from_session_info(
                    session.device_info if isinstance(session.device_info, dict) else {}
                )
                if not device:
                    device = device_from_user_agent(
                        user_agent or session.user_agent or ''
                    )
                if device:
                    idle_meta['device'] = device
                bg = None
                if isinstance(session.device_info, dict):
                    bg = session.device_info.get('browser_geo')
                if isinstance(bg, dict):
                    idle_meta['browser_geo'] = bg
            except Exception:  # noqa: BLE001
                idle_meta = {}
            get_audit_logger().record(
                event_type=EVENT_IDLE_TIMEOUT,
                user=session.user,
                phone_attempted=getattr(session.user, 'phone', '') or '',
                ip_address=audit_ip,
                location=audit_location,
                user_agent=user_agent or session.user_agent,
                session=session,
                message='Session terminated due to idle timeout.',
                metadata=idle_meta,
            )
            raise SessionIdleTimeout('Your session expired due to inactivity.')

        if touch:
            self.touch_activity(session)
        return session

    def touch_activity(self, session: UserSession) -> None:
        now = timezone.now()
        last = session.last_activity_at
        if last and (now - last).total_seconds() < ACTIVITY_TOUCH_THROTTLE_SECONDS:
            return
        UserSession.objects.filter(pk=session.pk, is_active=True).update(
            last_activity_at=now,
            updated_at=now,
        )
        session.last_activity_at = now

    def logout_session(
        self,
        session: UserSession,
        *,
        ip_address: str | None = None,
        location: dict | None = None,
        user_agent: str = '',
    ) -> None:
        self.terminate_session(session, reason=TERMINATION_LOGOUT)
        get_audit_logger().record(
            event_type='logout',
            user=session.user,
            phone_attempted=getattr(session.user, 'phone', '') or '',
            ip_address=ip_address,
            location=location,
            user_agent=user_agent,
            session=session,
            message='User logged out.',
        )

    def admin_terminate(self, session: UserSession, *, admin_user=None) -> None:
        self.terminate_session(session, reason=TERMINATION_ADMIN)
        get_audit_logger().record(
            event_type='session_rejected',
            user=session.user,
            phone_attempted=getattr(session.user, 'phone', '') or '',
            session=session,
            message='Session terminated by administrator.',
            metadata={'admin_id': getattr(admin_user, 'id', None)},
        )

    def update_session_network(
        self,
        session: UserSession,
        *,
        ip_address: str,
        location: dict,
        user_agent: str = '',
    ) -> None:
        session.ip_address = ip_address
        session.location = location or {}
        if user_agent:
            session.user_agent = user_agent[:2000]
        device = dict(session.device_info or {})
        device['ip'] = ip_address
        device['location'] = location or {}
        if user_agent:
            device['user_agent'] = user_agent[:500]
        session.device_info = device
        session.save(
            update_fields=[
                'ip_address',
                'location',
                'user_agent',
                'device_info',
                'updated_at',
            ]
        )


def get_session_lifecycle() -> SessionLifecycleService:
    return SessionLifecycleService()
