"""
Transactional email via admin-managed SMTP (SmtpConfig).
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from apps.admin_panel.models import SmtpConfig

logger = logging.getLogger(__name__)

# Always use real SMTP for admin-managed config (ignore settings.EMAIL_BACKEND, e.g. console in development).
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
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body_plain,
            from_email=config.from_email.strip(),
            to=[to],
            connection=connection,
        )
        if body_html:
            msg.attach_alternative(body_html, 'text/html')
        sent_count = msg.send(fail_silently=False)
        if not sent_count:
            raise EmailDeliveryError('SMTP server did not accept the message.')
        logger.info(
            'SMTP sent host=%s port=%s from=%s to=%s',
            config.host,
            config.port,
            config.from_email,
            to[:3] + '***',
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


def send_password_reset_otp_email(*, to_email: str, otp_code: str) -> None:
    expiry = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
    subject = 'mPayhub password reset verification code'
    body_plain = (
        f'Your password reset verification code is: {otp_code}\n\n'
        f'This code expires in {expiry} minutes.\n\n'
        'If you did not request this, ignore this email.'
    )
    body_html = (
        f'<p>Your password reset verification code is: <strong>{otp_code}</strong></p>'
        f'<p>This code expires in {expiry} minutes.</p>'
        '<p>If you did not request this, ignore this email.</p>'
    )
    send_email(to_email=to_email, subject=subject, body_plain=body_plain, body_html=body_html)
