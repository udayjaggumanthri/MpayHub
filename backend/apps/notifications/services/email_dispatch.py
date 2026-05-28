"""
Central email dispatch — never raises to callers for transactional notifications.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from apps.integrations.email_service import EmailDeliveryError, get_active_smtp_config, send_email
from apps.notifications.email_catalog import EMAIL_CATALOG_EVENT_KEYS
from apps.notifications.models import EmailDeliveryLog, EmailNotificationTemplate
from apps.notifications.services.email_idempotency import email_delivery_already_logged
from apps.notifications.services.template_render import render_template, strip_html_to_plain

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def mask_email(email: str) -> str:
    addr = (email or '').strip()
    if '@' not in addr:
        return '***'
    local, _, domain = addr.partition('@')
    if len(local) <= 2:
        masked_local = '*' * len(local)
    else:
        masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
    return f'{masked_local}@{domain}'


def _validate_email(to_email: str) -> tuple[Optional[str], str]:
    addr = (to_email or '').strip()
    if not addr:
        return None, 'no_email'
    if not _EMAIL_RE.match(addr):
        return None, 'invalid_email'
    return addr, ''


def _validate_context(template: EmailNotificationTemplate, context: dict[str, Any]) -> Optional[str]:
    schema = template.variable_schema if isinstance(template.variable_schema, list) else []
    ctx = context or {}
    for field in schema:
        if not isinstance(field, dict):
            continue
        name = field.get('name')
        if not name:
            continue
        if field.get('required') and str(ctx.get(name, '')).strip() == '':
            return 'invalid_context'
    return None


def _write_log(
    *,
    event_key: str,
    idempotency_key: str,
    user_id: Optional[int],
    to_email_masked: str,
    status: str,
    skip_reason: str = '',
    error_message: str = '',
    context_json: Optional[dict] = None,
) -> EmailDeliveryLog:
    return EmailDeliveryLog.objects.create(
        event_key=event_key,
        idempotency_key=idempotency_key,
        user_id=user_id,
        to_email_masked=to_email_masked,
        status=status,
        skip_reason=skip_reason,
        error_message=error_message,
        context_json=context_json or {},
    )


class EmailNotificationService:
    @staticmethod
    def dispatch(
        event_key: str,
        to_email: str,
        context: dict[str, Any],
        *,
        user_id: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        raise_on_failure: bool = False,
        for_test: bool = False,
    ) -> dict[str, Any]:
        try:
            return EmailNotificationService._dispatch_impl(
                event_key,
                to_email,
                context,
                user_id=user_id,
                idempotency_key=idempotency_key,
                raise_on_failure=raise_on_failure,
                for_test=for_test,
            )
        except EmailDeliveryError:
            raise
        except Exception as exc:
            logger.exception('Email dispatch unexpected error event=%s', event_key)
            result = {'status': 'failed', 'error': str(exc)}
            if raise_on_failure:
                raise EmailDeliveryError(str(exc)) from exc
            return result

    @staticmethod
    def _dispatch_impl(
        event_key: str,
        to_email: str,
        context: dict[str, Any],
        *,
        user_id: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        raise_on_failure: bool = False,
        for_test: bool = False,
    ) -> dict[str, Any]:
        if event_key not in EMAIL_CATALOG_EVENT_KEYS:
            return {'status': 'skipped', 'skip_reason': 'unknown_event'}

        addr, email_err = _validate_email(to_email)
        masked = mask_email(addr or to_email)

        idem = (
            (idempotency_key or '').strip()
            or f'{event_key}:{masked}:{hash(str(sorted((context or {}).items())))}'
        )
        if not for_test and email_delivery_already_logged(idem):
            logger.info(
                '[EMAIL] skipped (duplicate) event=%s to=%s idem=%s',
                event_key,
                masked,
                idem,
            )
            return {'status': 'skipped', 'skip_reason': 'duplicate'}

        if not addr:
            _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                to_email_masked=masked,
                status='skipped',
                skip_reason=email_err or 'no_email',
                context_json=context,
            )
            logger.info(
                '[EMAIL] skipped (%s) event=%s to=%s',
                email_err or 'no_email',
                event_key,
                masked,
            )
            return {'status': 'skipped', 'skip_reason': email_err or 'no_email'}

        smtp_cfg = get_active_smtp_config()
        if not smtp_cfg:
            _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                to_email_masked=masked,
                status='skipped',
                skip_reason='smtp_disabled',
                context_json=context,
            )
            if raise_on_failure:
                raise EmailDeliveryError(
                    'Email is not configured. Ask an administrator to set up SMTP in Admin settings.'
                )
            logger.info('[EMAIL] skipped (smtp_disabled) event=%s to=%s', event_key, masked)
            return {'status': 'skipped', 'skip_reason': 'smtp_disabled'}

        try:
            template = EmailNotificationTemplate.objects.get(event_key=event_key, is_deleted=False)
        except EmailNotificationTemplate.DoesNotExist:
            _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                to_email_masked=masked,
                status='skipped',
                skip_reason='template_not_seeded',
                context_json=context,
            )
            logger.info('[EMAIL] skipped (template_not_seeded) event=%s', event_key)
            return {'status': 'skipped', 'skip_reason': 'template_not_seeded'}

        if not template.is_enabled and not for_test:
            _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                to_email_masked=masked,
                status='skipped',
                skip_reason='event_disabled',
                context_json=context,
            )
            logger.info('[EMAIL] skipped (event_disabled) event=%s to=%s', event_key, masked)
            return {'status': 'skipped', 'skip_reason': 'event_disabled'}

        subject_tpl = (template.subject_template or '').strip()
        html_tpl = (template.body_html_template or '').strip()
        if not subject_tpl or not html_tpl:
            _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                to_email_masked=masked,
                status='skipped',
                skip_reason='empty_template',
                context_json=context,
            )
            logger.info('[EMAIL] skipped (empty_template) event=%s', event_key)
            return {'status': 'skipped', 'skip_reason': 'empty_template'}

        ctx_err = _validate_context(template, context)
        if ctx_err:
            _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                to_email_masked=masked,
                status='skipped',
                skip_reason=ctx_err,
                context_json=context,
            )
            logger.info(
                '[EMAIL] skipped (%s) event=%s to=%s ctx=%s',
                ctx_err,
                event_key,
                masked,
                context,
            )
            return {'status': 'skipped', 'skip_reason': ctx_err}

        ctx = {k: str(v) for k, v in (context or {}).items() if v is not None}
        subject = render_template(subject_tpl, ctx, escape_html=False)
        body_html = render_template(html_tpl, ctx, escape_html=True)
        body_plain = (template.body_plain_template or '').strip()
        if body_plain:
            body_plain = render_template(body_plain, ctx, escape_html=False)
        else:
            body_plain = strip_html_to_plain(body_html)

        try:
            send_email(
                to_email=addr,
                subject=subject,
                body_plain=body_plain,
                body_html=body_html,
                cfg=smtp_cfg,
            )
        except EmailDeliveryError as exc:
            log = _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                to_email_masked=masked,
                status='failed',
                error_message=str(exc),
                context_json=context,
            )
            if raise_on_failure:
                raise
            logger.warning('[EMAIL] failed event=%s to=%s error=%s', event_key, masked, exc)
            return {'status': 'failed', 'log_id': log.pk, 'error': str(exc)}

        log = _write_log(
            event_key=event_key,
            idempotency_key=idem,
            user_id=user_id,
            to_email_masked=masked,
            status='sent',
            context_json=context,
        )
        logger.info('[EMAIL] sent event=%s to=%s idem=%s log_id=%s', event_key, masked, idem, log.pk)
        return {'status': 'sent', 'log_id': log.pk}
