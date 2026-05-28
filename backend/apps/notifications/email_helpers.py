"""Shared helpers for resolving user email and login URL for templates."""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def user_display_name(user) -> str:
    name = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    if name:
        return name
    parts = [
        getattr(user, 'first_name', '') or '',
        getattr(user, 'last_name', '') or '',
    ]
    joined = ' '.join(p for p in parts if p).strip()
    return joined or getattr(user, 'user_id', '') or getattr(user, 'phone', '') or 'User'


def login_url_default() -> str:
    return getattr(settings, 'FRONTEND_LOGIN_URL', 'https://partner.mpayhub.in')


def dispatch_to_email(
    event_key: str,
    to_email: str,
    context: dict,
    *,
    user_id=None,
    idempotency_key: str,
) -> dict:
    """Dispatch to an explicit address. Never raises."""
    try:
        from apps.notifications.services.email_dispatch import EmailNotificationService

        addr = (to_email or '').strip()
        if not addr:
            return {'status': 'skipped', 'skip_reason': 'no_email'}
        return EmailNotificationService.dispatch(
            event_key,
            addr,
            context,
            user_id=user_id,
            idempotency_key=f'email:{idempotency_key}',
        )
    except Exception:
        logger.exception('[EMAIL] dispatch_to_email failed event=%s', event_key)
        return {'status': 'failed'}


def fresh_user_email(user_id) -> str:
    """Always read the current email from DB (not a cached user instance)."""
    if not user_id:
        return ''
    from django.contrib.auth import get_user_model

    row = get_user_model().objects.filter(pk=user_id).only('email').first()
    return (row.email or '').strip() if row else ''


def dispatch_user_email(
    event_key: str,
    user,
    context: dict,
    *,
    idempotency_key: str,
) -> None:
    """Dispatch transactional email to user if they have an email address. Never raises."""
    try:
        user_id = getattr(user, 'pk', None)
        to_email = fresh_user_email(user_id) or (getattr(user, 'email', None) or '').strip()
        if not to_email:
            logger.info(
                '[EMAIL] skipped (no_email on user) event=%s user_id=%s',
                event_key,
                user_id,
            )
            return
        # Include recipient so an email change on the profile gets a new send key.
        recipient_key = f'{idempotency_key}:{to_email.lower()}'
        result = dispatch_to_email(
            event_key,
            to_email,
            context,
            user_id=user_id,
            idempotency_key=recipient_key,
        )
        if result.get('status') != 'sent':
            logger.info(
                '[EMAIL] dispatch result event=%s user_id=%s status=%s reason=%s',
                event_key,
                user_id,
                result.get('status'),
                result.get('skip_reason') or result.get('error'),
            )
    except Exception:
        logger.exception('[EMAIL] dispatch_user_email failed event=%s', event_key)


def payin_success_recipient_email(load_money) -> str:
    """
    Pay-in email goes only to the wallet owner's current profile email (fresh DB read).
    We do not use LoadMoney.customer_email — that is a Razorpay/checkout snapshot and may be stale.
    """
    return fresh_user_email(getattr(load_money, 'user_id', None))


def mask_pan(pan: str) -> str:
    p = (pan or '').strip().upper()
    if len(p) < 5:
        return '****'
    return f'{p[:5]}****{p[-1]}' if len(p) >= 6 else f'{p[:2]}****'
