"""
Central SMS dispatch — never raises to callers for transactional notifications.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from django.conf import settings

from apps.notifications.catalog import CATALOG_EVENT_KEYS
from apps.notifications.models import SmsDeliveryLog, SmsNotificationTemplate, SmsProviderConfig
from apps.notifications.providers.console import ConsoleAdapter
from apps.notifications.providers.msg91 import Msg91Adapter
from apps.notifications.services.idempotency import delivery_already_logged
from apps.notifications.services.phone import mask_phone, normalize_phone

logger = logging.getLogger(__name__)


def _get_active_sms_config() -> Optional[SmsProviderConfig]:
    """Active + enabled profile used for transactional SMS (only one at a time)."""
    return (
        SmsProviderConfig.objects.filter(is_deleted=False, is_active=True, enabled=True)
        .order_by('-updated_at')
        .first()
    )


def _validate_context(template: SmsNotificationTemplate, context: dict[str, Any]) -> Optional[str]:
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


def _select_adapter(config: Optional[SmsProviderConfig]):
    if settings.DEBUG and (not config or not config.enabled):
        return ConsoleAdapter(), None
    if not config or not config.enabled:
        return None, 'global_disabled'
    if config.provider == 'console':
        return ConsoleAdapter(), None
    if config.provider == 'msg91':
        auth_key = config.get_auth_key()
        if not auth_key:
            return None, 'missing_auth_key'
        return (
            Msg91Adapter(
                auth_key=auth_key,
                api_base_url=config.api_base_url or 'https://control.msg91.com',
                route=config.route or '',
            ),
            None,
        )
    return None, 'unknown_provider'


def _write_log(
    *,
    event_key: str,
    idempotency_key: str,
    user_id: Optional[int],
    phone_masked: str,
    template_id: str,
    status: str,
    skip_reason: str = '',
    provider_message_id: str = '',
    error_message: str = '',
    context_json: Optional[dict] = None,
) -> SmsDeliveryLog:
    return SmsDeliveryLog.objects.create(
        event_key=event_key,
        idempotency_key=idempotency_key,
        user_id=user_id,
        phone_masked=phone_masked,
        template_id=template_id,
        status=status,
        skip_reason=skip_reason,
        provider_message_id=provider_message_id,
        error_message=error_message,
        context_json=context_json or {},
    )


class SmsNotificationService:
    @staticmethod
    def dispatch(
        event_key: str,
        phone: str,
        context: dict[str, Any],
        *,
        user_id: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Send SMS for a catalog event. Returns result dict; does not raise.
        """
        try:
            return SmsNotificationService._dispatch_impl(
                event_key,
                phone,
                context,
                user_id=user_id,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:
            logger.exception('SMS dispatch unexpected error event=%s', event_key)
            return {'status': 'failed', 'error': str(exc)}

    @staticmethod
    def _dispatch_impl(
        event_key: str,
        phone: str,
        context: dict[str, Any],
        *,
        user_id: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        if event_key not in CATALOG_EVENT_KEYS:
            return {'status': 'skipped', 'skip_reason': 'unknown_event'}

        config = _get_active_sms_config()
        cc = (config.country_code if config else None) or '91'
        phone_e164, phone_err = normalize_phone(phone, cc)
        masked = mask_phone(phone_e164 or phone)

        idem = (idempotency_key or '').strip() or f'{event_key}:{masked}:{hash(str(sorted((context or {}).items())))}'
        if delivery_already_logged(idem):
            return {'status': 'skipped', 'skip_reason': 'duplicate'}

        if not phone_e164:
            _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                phone_masked=masked,
                template_id='',
                status='skipped',
                skip_reason=phone_err or 'invalid_phone',
                context_json=context,
            )
            if settings.DEBUG:
                print(f'[SMS] skipped invalid phone event={event_key} phone={phone}')
            return {'status': 'skipped', 'skip_reason': phone_err or 'invalid_phone'}

        adapter, adapter_skip = _select_adapter(config)
        if adapter_skip:
            _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                phone_masked=masked,
                template_id='',
                status='skipped',
                skip_reason=adapter_skip,
                context_json=context,
            )
            if settings.DEBUG:
                print(f'[SMS] skipped ({adapter_skip}) event={event_key} phone={phone_e164} ctx={context}')
            return {'status': 'skipped', 'skip_reason': adapter_skip}

        try:
            template = SmsNotificationTemplate.objects.get(event_key=event_key, is_deleted=False)
        except SmsNotificationTemplate.DoesNotExist:
            _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                phone_masked=masked,
                template_id='',
                status='skipped',
                skip_reason='template_not_seeded',
                context_json=context,
            )
            return {'status': 'skipped', 'skip_reason': 'template_not_seeded'}

        if not template.is_enabled or not (template.template_id or '').strip():
            _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                phone_masked=masked,
                template_id=template.template_id or '',
                status='skipped',
                skip_reason='event_disabled',
                context_json=context,
            )
            if settings.DEBUG:
                print(f'[SMS] skipped (event disabled) event={event_key} phone={phone_e164} ctx={context}')
            return {'status': 'skipped', 'skip_reason': 'event_disabled'}

        ctx_err = _validate_context(template, context)
        if ctx_err:
            _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                phone_masked=masked,
                template_id=template.template_id,
                status='skipped',
                skip_reason=ctx_err,
                context_json=context,
            )
            return {'status': 'skipped', 'skip_reason': ctx_err}

        variables = {k: str(v) for k, v in (context or {}).items() if v is not None}
        sender_id = (config.sender_id if config else '') or ''
        result = adapter.send_template(
            phone_e164,
            template.template_id,
            variables,
            sender_id=sender_id,
        )

        if result.success:
            log = _write_log(
                event_key=event_key,
                idempotency_key=idem,
                user_id=user_id,
                phone_masked=masked,
                template_id=template.template_id,
                status='sent',
                provider_message_id=result.message_id,
                context_json=context,
            )
            return {'status': 'sent', 'log_id': log.pk, 'provider_message_id': result.message_id}

        log = _write_log(
            event_key=event_key,
            idempotency_key=idem,
            user_id=user_id,
            phone_masked=masked,
            template_id=template.template_id,
            status='failed',
            error_message=result.error,
            context_json=context,
        )
        return {'status': 'failed', 'log_id': log.pk, 'error': result.error}

    @staticmethod
    def send_raw_template(
        phone: str,
        template_id: str,
        variables: Optional[dict[str, Any]] = None,
        *,
        user_id: Optional[int] = None,
        cfg: Optional[SmsProviderConfig] = None,
    ) -> dict[str, Any]:
        """Admin test send — bypasses event template row; uses explicit or active provider config."""
        try:
            config = cfg or _get_active_sms_config()
            cc = (config.country_code if config else None) or '91'
            phone_e164, phone_err = normalize_phone(phone, cc)
            if not phone_e164:
                return {'sent': False, 'error': phone_err or 'invalid_phone'}

            adapter, adapter_skip = _select_adapter(config)
            if adapter_skip:
                if settings.DEBUG:
                    adapter = ConsoleAdapter()
                else:
                    return {'sent': False, 'error': adapter_skip}

            result = adapter.send_template(
                phone_e164,
                template_id,
                variables or {},
                sender_id=(config.sender_id if config else '') or '',
            )
            if config:
                from django.utils import timezone

                config.last_test_at = timezone.now()
                config.last_test_status = 'ok' if result.success else 'failed'
                config.last_test_error = '' if result.success else (result.error or '')
                config.save(update_fields=['last_test_at', 'last_test_status', 'last_test_error', 'updated_at'])

            if result.success:
                return {'sent': True, 'provider_message_id': result.message_id}
            return {'sent': False, 'error': result.error}
        except Exception as exc:
            logger.exception('SMS raw template send failed')
            return {'sent': False, 'error': str(exc)}
