"""
Transactional email via admin-managed SMTP (SmtpConfig) and template dispatch.
"""
from __future__ import annotations

import logging
import uuid

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils.html import strip_tags

from apps.admin_panel.models import SmtpConfig

logger = logging.getLogger(__name__)

SMTP_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
SMTP_TIMEOUT_SECONDS = 30


class EmailDeliveryError(Exception):
    """SMTP send failed or SMTP is not configured."""


def get_active_smtp_config() -> SmtpConfig | None:
    return (
        SmtpConfig.objects.filter(is_deleted=False, is_active=True, enabled=True)
        .order_by('-updated_at')
        .first()
    )


def _connection_from_config(cfg: SmtpConfig):
    password = cfg.get_password()
    if not cfg.username or not password:
        raise EmailDeliveryError('SMTP username and password must be configured.')
    if not (cfg.from_email or '').strip():
        raise EmailDeliveryError('SMTP from_email must be configured.')
    return get_connection(
        backend=SMTP_BACKEND,
        host=(cfg.host or '').strip(),
        port=int(cfg.port),
        username=(cfg.username or '').strip(),
        password=password,
        use_tls=bool(cfg.use_tls),
        use_ssl=bool(cfg.use_ssl),
        timeout=SMTP_TIMEOUT_SECONDS,
        fail_silently=False,
    )


def send_email(
    *,
    to_email: str,
    subject: str,
    body_plain: str,
    body_html: str | None = None,
    cfg: SmtpConfig | None = None,
) -> None:
    """Send email using active SmtpConfig (or explicit cfg)."""
    config = cfg or get_active_smtp_config()
    if not config:
        raise EmailDeliveryError(
            'Email is not configured. Ask an administrator to set up SMTP in Admin settings.'
        )
    to = (to_email or '').strip()
    if not to:
        raise EmailDeliveryError('Recipient email is required.')

    try:
        connection = _connection_from_config(config)
        from_addr = config.from_email.strip()
        from_name = getattr(settings, 'EMAIL_NOTIFICATION_FROM_NAME', 'mPayHub')
        from_header = f'{from_name} <{from_addr}>' if from_name else from_addr
        plain = body_plain or strip_tags(body_html or '') or subject
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain,
            from_email=from_header,
            to=[to],
            connection=connection,
            reply_to=[from_addr],
            headers={
                'X-Mailer': 'mPayHub',
                'Message-ID': f'<mpayhub.{uuid.uuid4().hex}@mpayhub.in>',
            },
        )
        if body_html:
            msg.attach_alternative(body_html, 'text/html')
        sent_count = msg.send(fail_silently=False)
        if not sent_count:
            raise EmailDeliveryError('SMTP server did not accept the message.')
        domain = to.split('@')[-1] if '@' in to else '?'
        logger.info(
            'SMTP sent host=%s port=%s from=%s to=%s***@%s',
            config.host,
            config.port,
            config.from_email,
            to[:3],
            domain,
        )
    except EmailDeliveryError:
        raise
    except Exception as exc:
        logger.exception('SMTP send failed to %s', to[:3] + '***')
        hint = _smtp_error_hint(exc, config)
        raise EmailDeliveryError(f'Failed to send email: {exc}.{hint}') from exc


def _smtp_error_hint(exc: Exception, config: SmtpConfig) -> str:
    err = str(exc).lower()
    host = (getattr(config, 'host', '') or '').lower()
    is_zoho = 'zoho' in host

    if '5.7.8' in err or 'access restricted' in err:
        if is_zoho:
            return (
                ' Zoho blocked SMTP login (554 5.7.8). In Zoho Mail: Settings → Mail Accounts → '
                f'{config.username or "your mailbox"} → enable IMAP Access; then Security → '
                'App Passwords → create one and paste it in Admin → SMTP password (not your login password). '
                'Org admins: allow IMAP/SMTP under Email Policy. See help.zoho.com/mail/help/imap-access.html'
            )
        return ' SMTP access is restricted by your mail provider. Enable SMTP/IMAP or use an app password.'

    if 'authentication' in err or '535' in err or '534' in err or 'auth' in err:
        if is_zoho:
            return (
                ' Use the full mailbox as username (e.g. noreply@mpayhub.in) and a Zoho App Password '
                'if 2FA is on. Enable IMAP Access on that mailbox in Zoho Mail settings.'
            )
        return ' Check username/password; many providers require an app-specific password.'

    if 'ssl' in err or 'tls' in err or 'wrong version' in err:
        if is_zoho:
            return ' For Zoho org mail use smtppro.zoho.in with 587+TLS or 465+SSL (only one).'
        return ' Check port and TLS/SSL settings (587+TLS or 465+SSL, not both).'

    return ''


def _legacy_auth_otp_email(*, purpose: str, to_email: str, otp_code: str) -> None:
    expiry = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
    if purpose == 'mpin-reset':
        subject = 'mPayhub MPIN reset verification code'
        label = 'MPIN reset'
    else:
        subject = 'mPayhub password reset verification code'
        label = 'password reset'
    body_plain = (
        f'Your {label} verification code is: {otp_code}\n\n'
        f'This code expires in {expiry} minutes.\n\n'
        'If you did not request this, ignore this email.'
    )
    body_html = (
        f'<p>Your {label} verification code is: <strong>{otp_code}</strong></p>'
        f'<p>This code expires in {expiry} minutes.</p>'
        '<p>If you did not request this, ignore this email.</p>'
    )
    send_email(to_email=to_email, subject=subject, body_plain=body_plain, body_html=body_html)


def send_auth_otp_email(*, purpose: str, to_email: str, otp_code: str) -> None:
    """Dispatch admin-configurable auth OTP email (password or MPIN reset)."""
    from apps.authentication.constants import AUTH_OTP_PURPOSE_TO_EMAIL_EVENT
    from apps.notifications.services.email_dispatch import EmailNotificationService

    event_key = AUTH_OTP_PURPOSE_TO_EMAIL_EVENT.get(purpose)
    if not event_key:
        raise EmailDeliveryError(f'Email OTP is not supported for purpose: {purpose}')

    expiry = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
    result = EmailNotificationService.dispatch(
        event_key,
        to_email,
        {'otp': otp_code, 'expiry_minutes': str(expiry)},
        idempotency_key=f'{event_key}:{to_email}:{otp_code}',
        raise_on_failure=False,
    )
    if result.get('status') == 'sent':
        return
    if result.get('skip_reason') in (
        'event_disabled',
        'template_not_seeded',
        'empty_template',
    ):
        _legacy_auth_otp_email(purpose=purpose, to_email=to_email, otp_code=otp_code)
        return
    if result.get('status') == 'failed':
        raise EmailDeliveryError(result.get('error') or 'Failed to send verification email')
    if result.get('skip_reason') == 'smtp_disabled':
        raise EmailDeliveryError(
            'Email is not configured. Ask an administrator to set up SMTP in Admin settings.'
        )
    if result.get('skip_reason') == 'duplicate':
        return
    if result.get('skip_reason') in ('no_email', 'invalid_email'):
        raise EmailDeliveryError('Recipient email is required.')
    _legacy_auth_otp_email(purpose=purpose, to_email=to_email, otp_code=otp_code)


def send_password_reset_otp_email(*, to_email: str, otp_code: str) -> None:
    send_auth_otp_email(purpose='password-reset', to_email=to_email, otp_code=otp_code)


def send_mpin_reset_otp_email(*, to_email: str, otp_code: str) -> None:
    send_auth_otp_email(purpose='mpin-reset', to_email=to_email, otp_code=otp_code)
