"""
Who receives pay-in **platform** amounts (gateway fee + admin / absorbed pool) on the commission wallet.

Decoupled from fee math so ops can extend resolution (env, role rules, onboarding parent) without
touching distribution formulas.
"""
import logging
from typing import List, Optional

from django.conf import settings

from apps.authentication.models import User
from apps.fund_management.payin_hierarchy import upline_chain

logger = logging.getLogger(__name__)


def resolve_platform_payin_recipients(payer_user: Optional[User] = None) -> List[User]:
    """
    Resolution order:
    1. ``PLATFORM_PAYIN_SETTLEMENT_USER_ID`` (pk) — single recipient, full platform slices.
    2. All active users with role Admin (case-insensitive).
    3. All active superusers (split if multiple).
    4. First active Admin in the payer's upline (onboarding parent chain) — full slices to that user.
    5. Empty — amounts stay on CommissionLedger with ``user=None`` (logged).
    """
    uid = getattr(settings, 'PLATFORM_PAYIN_SETTLEMENT_USER_ID', None)
    if uid is not None:
        try:
            pk = int(uid)
        except (TypeError, ValueError):
            pk = 0
        if pk > 0:
            u = User.objects.filter(pk=pk, is_active=True).first()
            if u:
                return [u]
            logger.warning(
                'PLATFORM_PAYIN_SETTLEMENT_USER_ID=%s did not match an active user; using fallbacks.',
                uid,
            )

    admins = list(
        User.objects.filter(is_active=True, role__iexact='Admin').order_by('id').distinct()
    )
    if admins:
        return admins

    supers = list(User.objects.filter(is_active=True, is_superuser=True).order_by('id'))
    if supers:
        return supers

    if payer_user:
        for parent in upline_chain(payer_user):
            if not parent.is_active:
                continue
            role = (getattr(parent, 'role', None) or '').strip().lower()
            if role == 'admin':
                logger.info(
                    'pay_in_settlement: using onboarding Admin parent user_id=%s for platform slices',
                    parent.pk,
                )
                return [parent]

    return []


def log_missing_platform_recipients(
    *,
    transaction_id: str,
    payer_id: Optional[int],
    gateway_amount,
    admin_amount,
) -> None:
    if gateway_amount > 0 or admin_amount > 0:
        logger.warning(
            'pay_in_settlement: no recipients for platform slices (commission wallet will stay 0). '
            'txn=%s payer_id=%s gw=%s admin_total=%s — set PLATFORM_PAYIN_SETTLEMENT_USER_ID or ensure '
            'an active Admin / superuser exists.',
            transaction_id,
            payer_id,
            gateway_amount,
            admin_amount,
        )
