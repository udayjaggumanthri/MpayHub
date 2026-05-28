"""
System-wide maintenance mode — single source of truth for module availability.

Layer 1 (this module) sits above per-user financial_access and per-provider gateway status.
"""
from __future__ import annotations

from typing import Any

from django.core.cache import cache
from rest_framework.exceptions import PermissionDenied

MODULE_PAY_IN = 'pay_in'
MODULE_PAYOUT = 'payout'
MODULE_BBPS = 'bbps'

VALID_MODULES = frozenset({MODULE_PAY_IN, MODULE_PAYOUT, MODULE_BBPS})

ACCESS_CODE_MODULE_MAINTENANCE = 'MODULE_MAINTENANCE'

DEFAULT_MESSAGES = {
    MODULE_PAY_IN: 'Pay-in is temporarily unavailable due to maintenance. Please try again later.',
    MODULE_PAYOUT: 'Payout is temporarily unavailable due to maintenance. Please try again later.',
    MODULE_BBPS: 'BBPS is temporarily unavailable due to maintenance. Please try again later.',
}

CACHE_KEY = 'system_maintenance_status_v1'
CACHE_TTL_SECONDS = 8


def _permission_denied(module: str, message: str) -> PermissionDenied:
    return PermissionDenied(
        detail={
            'code': ACCESS_CODE_MODULE_MAINTENANCE,
            'module': module,
            'message': message,
        }
    )


def get_config():
    """Load or create the singleton maintenance config row."""
    from apps.core.models import SystemMaintenanceConfig

    config, _ = SystemMaintenanceConfig.objects.get_or_create(
        pk=SystemMaintenanceConfig.SINGLETON_PK,
        defaults={
            'pay_in_enabled': True,
            'payout_enabled': True,
            'bbps_enabled': True,
        },
    )
    return config


def invalidate_cache() -> None:
    cache.delete(f'{CACHE_KEY}_public')
    cache.delete(f'{CACHE_KEY}_admin')


def _build_status_dict(config, *, include_internal: bool = False) -> dict[str, Any]:
    pay_in_msg = (config.pay_in_message or '').strip() or DEFAULT_MESSAGES[MODULE_PAY_IN]
    payout_msg = (config.payout_message or '').strip() or DEFAULT_MESSAGES[MODULE_PAYOUT]
    bbps_msg = (config.bbps_message or '').strip() or DEFAULT_MESSAGES[MODULE_BBPS]

    out: dict[str, Any] = {
        'pay_in': {
            'enabled': bool(config.pay_in_enabled),
            'message': pay_in_msg,
        },
        'payout': {
            'enabled': bool(config.payout_enabled),
            'message': payout_msg,
        },
        'bbps': {
            'enabled': bool(config.bbps_enabled),
            'message': bbps_msg,
        },
        'updated_at': config.updated_at.isoformat() if config.updated_at else None,
    }

    if include_internal:
        updated_by = config.updated_by
        out['reason_internal'] = (config.reason_internal or '').strip()
        out['updated_by'] = None
        if updated_by:
            out['updated_by'] = {
                'id': updated_by.pk,
                'user_id': getattr(updated_by, 'user_id', None),
                'name': f'{updated_by.first_name or ""} {updated_by.last_name or ""}'.strip()
                or str(updated_by.phone or updated_by.pk),
            }

    return out


def get_status(*, include_internal: bool = False, use_cache: bool = True) -> dict[str, Any]:
    """Return maintenance flags and user-facing messages."""
    cache_suffix = '_admin' if include_internal else '_public'
    cache_key = f'{CACHE_KEY}{cache_suffix}'

    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    config = get_config()
    status = _build_status_dict(config, include_internal=include_internal)

    if use_cache:
        cache.set(cache_key, status, CACHE_TTL_SECONDS)

    return status


def is_module_enabled(module: str) -> bool:
    if module not in VALID_MODULES:
        raise ValueError(f'Unknown maintenance module: {module}')
    status = get_status()
    return bool(status[module]['enabled'])


def get_module_message(module: str) -> str:
    if module not in VALID_MODULES:
        raise ValueError(f'Unknown maintenance module: {module}')
    status = get_status()
    return str(status[module]['message'])


def assert_module_available(module: str) -> None:
    """Raise PermissionDenied if the module is in maintenance (disabled)."""
    if module not in VALID_MODULES:
        raise ValueError(f'Unknown maintenance module: {module}')
    if is_module_enabled(module):
        return
    raise _permission_denied(module, get_module_message(module))


def assert_pay_in_available(*, user, transaction_id: str | None = None) -> None:
    """
    Block new pay-in activity unless completing an in-flight PENDING LoadMoney order.
    """
    if transaction_id and user:
        from apps.fund_management.models import LoadMoney

        if LoadMoney.objects.filter(
            user=user,
            transaction_id=transaction_id,
            status='PENDING',
            is_deleted=False,
        ).exists():
            return
    assert_module_available(MODULE_PAY_IN)


def record_audit(
    *,
    module: str,
    enabled: bool,
    user_message: str = '',
    reason_internal: str = '',
    changed_by=None,
) -> None:
    from apps.core.models import SystemMaintenanceAuditLog

    SystemMaintenanceAuditLog.objects.create(
        module=module,
        enabled=enabled,
        user_message=user_message or '',
        reason_internal=reason_internal or '',
        changed_by=changed_by,
    )


def update_config(*, changed_by, patch: dict) -> dict[str, Any]:
    """
    Apply admin patch to singleton config. Logs per-module changes.
    Returns admin status dict (include_internal=True).
    """
    config = get_config()

    field_map = {
        'pay_in_enabled': MODULE_PAY_IN,
        'payout_enabled': MODULE_PAYOUT,
        'bbps_enabled': MODULE_BBPS,
    }
    message_map = {
        MODULE_PAY_IN: 'pay_in_message',
        MODULE_PAYOUT: 'payout_message',
        MODULE_BBPS: 'bbps_message',
    }

    update_fields = ['updated_at']
    if 'reason_internal' in patch:
        config.reason_internal = patch.get('reason_internal') or ''
        update_fields.append('reason_internal')

    for bool_field, mod in field_map.items():
        if bool_field in patch:
            new_val = bool(patch[bool_field])
            old_val = getattr(config, bool_field)
            setattr(config, bool_field, new_val)
            update_fields.append(bool_field)
            if new_val != old_val:
                msg_field = message_map[mod]
                user_msg = (getattr(config, msg_field) or '').strip() or DEFAULT_MESSAGES[mod]
                record_audit(
                    module=mod,
                    enabled=new_val,
                    user_message=user_msg,
                    reason_internal=(config.reason_internal or '').strip(),
                    changed_by=changed_by,
                )

    for msg_field in message_map.values():
        if msg_field in patch:
            setattr(config, msg_field, patch.get(msg_field) or '')
            update_fields.append(msg_field)

    if changed_by is not None:
        config.updated_by = changed_by
        update_fields.append('updated_by')

    config.save(update_fields=list(dict.fromkeys(update_fields)))
    invalidate_cache()
    return get_status(include_internal=True, use_cache=False)
