"""
Helpers to record user activity (money / admin) into the unified audit log.

Never raises to callers — audit must not break money settlement.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from apps.session_security.constants import (
    EVENT_ACCESS_CONTROLS_CHANGED,
    EVENT_BANK_ACCOUNT_ADDED,
    EVENT_BANK_ACCOUNT_DELETED,
    EVENT_BANK_ACCOUNT_UPDATED,
    EVENT_BBPS_PAYMENT,
    EVENT_CONTACT_CREATED,
    EVENT_CONTACT_DELETED,
    EVENT_CONTACT_UPDATED,
    EVENT_PAYIN_CREATED,
    EVENT_PAYIN_FAILED,
    EVENT_PAYIN_SUCCESS,
    EVENT_PAYOUT_CREATED,
    EVENT_PAYOUT_FAILED,
    EVENT_PAYOUT_SUCCESS,
    EVENT_REPORT_VIEWED,
    EVENT_ROLE_CHANGED,
    EVENT_USER_DISABLED,
    EVENT_USER_ENABLED,
    EVENT_WALLET_TRANSFER,
)
from apps.session_security.services.audit import get_audit_logger
from apps.session_security.services.geo import soft_lookup_location
from apps.session_security.services.request_context import get_request_network

logger = logging.getLogger(__name__)


def _attach_network_from_request(
    *,
    ip_address: str | None,
    location: dict | None,
    user_agent: str,
    metadata: dict,
) -> tuple[str | None, dict, str, dict]:
    """
    Prefer explicit args; else pull IP/UA/geo from request middleware context.
    Marks metadata.network_capture for UI/ops clarity.
    """
    meta = dict(metadata or {})
    if ip_address:
        loc = location if isinstance(location, dict) and location else soft_lookup_location(ip_address)
        meta.setdefault('network_capture', 'explicit')
        return ip_address, loc, user_agent or '', meta

    ctx = get_request_network(resolve_geo=True)
    ctx_ip = ctx.get('ip_address')
    ctx_ua = ctx.get('user_agent') or ''
    ctx_loc = ctx.get('location') if isinstance(ctx.get('location'), dict) else {}

    if ctx_ip:
        loc = ctx_loc if ctx_loc else soft_lookup_location(ctx_ip)
        meta.setdefault('network_capture', 'request')
        return ctx_ip, loc, user_agent or ctx_ua, meta

    # Webhook / celery / management command — no client network
    meta.setdefault('network_capture', 'unavailable')
    empty = soft_lookup_location(None)
    empty['source'] = 'server_side'
    return None, empty, user_agent or '', meta


def record_user_activity(
    *,
    user,
    event_type: str,
    message: str = '',
    metadata: dict | None = None,
    ip_address: str | None = None,
    location: dict | None = None,
    user_agent: str = '',
    phone_attempted: str = '',
) -> None:
    try:
        ip, loc, ua, meta = _attach_network_from_request(
            ip_address=ip_address,
            location=location,
            user_agent=user_agent,
            metadata=metadata or {},
        )
        get_audit_logger().record(
            event_type=event_type,
            user=user,
            phone_attempted=phone_attempted or getattr(user, 'phone', '') or '',
            ip_address=ip,
            location=loc or {},
            user_agent=ua,
            message=message,
            metadata=meta,
        )
    except Exception:  # noqa: BLE001
        logger.exception('record_user_activity failed for %s', event_type)


def _dec(val) -> str:
    try:
        if val is None:
            return ''
        return str(Decimal(str(val)))
    except Exception:  # noqa: BLE001
        return str(val or '')


def _money_meta_from_passbook(entry) -> dict[str, Any]:
    debit = getattr(entry, 'debit_amount', None) or Decimal('0')
    credit = getattr(entry, 'credit_amount', None) or Decimal('0')
    amount = debit if Decimal(str(debit)) > 0 else credit
    return {
        'passbook_id': getattr(entry, 'id', None),
        'wallet_type': getattr(entry, 'wallet_type', '') or '',
        'service': getattr(entry, 'service', '') or '',
        'service_id': getattr(entry, 'service_id', '') or '',
        'amount': _dec(amount),
        'debit_amount': _dec(debit),
        'credit_amount': _dec(credit),
        'opening_balance': _dec(getattr(entry, 'opening_balance', None)),
        'closing_balance': _dec(getattr(entry, 'closing_balance', None)),
        'description': (getattr(entry, 'description', '') or '')[:200],
        'initiator_user_id': getattr(entry, 'initiator_user_id', None),
    }


def map_passbook_event_type(entry) -> str | None:
    """
    Map a PassbookEntry to an activity event type.
    Returns None when the entry should not be audited.
    """
    service = (getattr(entry, 'service', '') or '').strip().upper()
    description = (getattr(entry, 'description', '') or '').lower()
    wallet = (getattr(entry, 'wallet_type', '') or '').strip().lower()
    debit = Decimal(str(getattr(entry, 'debit_amount', 0) or 0))
    credit = Decimal(str(getattr(entry, 'credit_amount', 0) or 0))

    # Skip commission / profit hierarchy noise (user-facing money is main/bbps)
    if wallet in ('commission', 'profit') and service not in ('PAYOUT', 'BBPS', 'WALLET_TRANSFER'):
        # Still allow explicit load-money style credits on commission if needed later
        if 'LOAD' not in service and 'PAYIN' not in service and 'PAY IN' not in service:
            return None

    if service in ('WALLET_TRANSFER',) or 'wallet transfer' in description or 'transfer to bbps' in description:
        # One event per transfer: prefer debit side
        if debit <= 0:
            return None
        return EVENT_WALLET_TRANSFER

    if service in ('BBPS',) or description.startswith('paid for'):
        return EVENT_BBPS_PAYMENT

    if service in ('PAYOUT',) or 'payout' in description:
        if 'fail' in description:
            return EVENT_PAYOUT_FAILED
        return EVENT_PAYOUT_SUCCESS

    if service in ('BANK VERIFICATION',):
        return None

    if (
        service in ('PAYIN', 'PAY IN', 'LOAD_MONEY', 'LOAD MONEY', 'LOADMONEY')
        or 'payin' in description
        or 'pay-in' in description
        or 'load money' in description
        or 'gateway' in description and credit > 0 and wallet == 'main'
    ):
        if 'fail' in description:
            return EVENT_PAYIN_FAILED
        if 'creat' in description or 'pending' in description:
            return EVENT_PAYIN_CREATED
        return EVENT_PAYIN_SUCCESS

    # Generic main/bbps wallet movement
    if wallet in ('main', 'bbps') and (debit > 0 or credit > 0):
        if credit > 0:
            return EVENT_PAYIN_SUCCESS
        return EVENT_PAYOUT_SUCCESS

    return None


def record_passbook_activity(entry) -> None:
    """Call after PassbookEntry create (or from post_save signal)."""
    try:
        event_type = map_passbook_event_type(entry)
        if not event_type:
            return
        user = getattr(entry, 'user', None)
        if user is None:
            return
        record_user_activity(
            user=user,
            event_type=event_type,
            message=(getattr(entry, 'description', '') or event_type)[:500],
            metadata=_money_meta_from_passbook(entry),
        )
    except Exception:  # noqa: BLE001
        logger.exception('record_passbook_activity failed')


def record_admin_access_change(*, target, actor=None, before: dict | None = None, after: dict | None = None):
    before = before or {}
    after = after or {}
    event_type = EVENT_ACCESS_CONTROLS_CHANGED
    if before.get('is_active') is True and after.get('is_active') is False:
        event_type = EVENT_USER_DISABLED
    elif before.get('is_active') is False and after.get('is_active') is True:
        event_type = EVENT_USER_ENABLED
    record_user_activity(
        user=target,
        event_type=event_type,
        message='Account access controls updated',
        metadata={
            'actor_id': getattr(actor, 'id', None),
            'before': before,
            'after': after,
        },
    )


def record_role_change(*, target, actor=None, old_role: str = '', new_role: str = ''):
    record_user_activity(
        user=target,
        event_type=EVENT_ROLE_CHANGED,
        message=f'Role changed from {old_role} to {new_role}',
        metadata={
            'actor_id': getattr(actor, 'id', None),
            'old_role': old_role,
            'new_role': new_role,
        },
    )


def record_contact_activity(*, user, action: str, contact=None, contact_id=None):
    """action: created | updated | deleted"""
    mapping = {
        'created': EVENT_CONTACT_CREATED,
        'updated': EVENT_CONTACT_UPDATED,
        'deleted': EVENT_CONTACT_DELETED,
    }
    event_type = mapping.get(action)
    if not event_type or user is None:
        return
    name = ''
    phone = ''
    cid = contact_id
    if contact is not None:
        name = (getattr(contact, 'name', '') or '')[:120]
        phone = (getattr(contact, 'phone', '') or '')[:20]
        cid = getattr(contact, 'id', cid)
    record_user_activity(
        user=user,
        event_type=event_type,
        message=f'Contact {action}' + (f': {name}' if name else ''),
        metadata={'contact_id': cid, 'name': name, 'phone': phone},
    )


def record_bank_account_activity(*, user, action: str, account=None, account_id=None):
    mapping = {
        'created': EVENT_BANK_ACCOUNT_ADDED,
        'updated': EVENT_BANK_ACCOUNT_UPDATED,
        'deleted': EVENT_BANK_ACCOUNT_DELETED,
    }
    event_type = mapping.get(action)
    if not event_type or user is None:
        return
    bank = ''
    masked = ''
    aid = account_id
    if account is not None:
        bank = (getattr(account, 'bank_name', '') or '')[:80]
        num = str(getattr(account, 'account_number', '') or '')
        masked = (('*' * max(0, len(num) - 4)) + num[-4:]) if num else ''
        aid = getattr(account, 'id', aid)
    record_user_activity(
        user=user,
        event_type=event_type,
        message=f'Bank account {action}' + (f': {bank}' if bank else ''),
        metadata={'bank_account_id': aid, 'bank_name': bank, 'account_masked': masked},
    )


def record_report_viewed(*, user, report_type: str, scope: str = ''):
    """
    Soft-fail + throttle: at most one audit row per user/report_type per 10 minutes.
    Avoids flooding logs when report UIs poll.
    """
    if user is None or not report_type:
        return
    try:
        from django.core.cache import cache

        key = f'audit:report_view:{getattr(user, "id", 0)}:{report_type}'
        if cache.get(key):
            return
        cache.set(key, 1, 600)
    except Exception:  # noqa: BLE001
        pass
    label = str(report_type).replace('_', ' ').strip() or 'report'
    record_user_activity(
        user=user,
        event_type=EVENT_REPORT_VIEWED,
        message=f'Viewed {label} report',
        metadata={'report_type': report_type, 'scope': scope or ''},
    )
