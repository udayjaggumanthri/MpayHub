"""
BBPS provider float (company BillAvenue prepaid balance tracking).

Admin sets/overrides the tracked balance manually. Payments are gated when
enforcement is on; successful payments debit and refunds credit — idempotently.
Float tracking never raises into the live payment settlement path.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.bbps.catalog.env import active_bbps_environment
from apps.bbps.models import BbpsPaymentAttempt, BbpsProviderFloat, BbpsProviderFloatLedger
from apps.fund_management.money_utils import money_q
from apps.integrations.billavenue.registry import normalize_billavenue_mode

logger = logging.getLogger(__name__)

USER_FACING_FLOAT_UNAVAILABLE = (
    'Bill payment service is temporarily unavailable. Please try again shortly.'
)


class BbpsProviderFloatInsufficient(Exception):
    """Raised when company float cannot cover a BBPS payment (enforcement on)."""

    def __init__(self, message: str = USER_FACING_FLOAT_UNAVAILABLE, *, shortfall: Decimal | None = None):
        super().__init__(message)
        self.shortfall = shortfall
        self.code = 'BBPS_PROVIDER_FLOAT_INSUFFICIENT'


def _env(environment: str | None = None) -> str:
    return normalize_billavenue_mode(environment or active_bbps_environment())


def _admin_name(user) -> str:
    if not user:
        return ''
    try:
        from apps.transactions.agent_snapshot import display_name_for_user

        return display_name_for_user(user)[:255]
    except Exception:
        return (
            (getattr(user, 'get_full_name', lambda: '')() or '')
            or getattr(user, 'user_id', '')
            or getattr(user, 'phone', '')
            or str(getattr(user, 'pk', ''))
        )[:255]


def get_or_create_float(environment: str | None = None) -> BbpsProviderFloat:
    env = _env(environment)
    row, _ = BbpsProviderFloat.objects.get_or_create(
        environment=env,
        defaults={
            'balance': Decimal('0'),
            'low_balance_threshold': Decimal('0'),
            'enforcement_enabled': True,
        },
    )
    return row


def get_float_status(environment: str | None = None) -> dict[str, Any]:
    env = _env(environment)
    row = get_or_create_float(env)
    balance = money_q(row.balance)
    threshold = money_q(row.low_balance_threshold)
    today = timezone.localdate()
    debit_agg = (
        BbpsProviderFloatLedger.objects.filter(
            is_deleted=False,
            environment=env,
            entry_type='AUTO_DEBIT',
            created_at__date=today,
        ).aggregate(total=Sum('amount'))
    )
    today_spend = money_q(debit_agg.get('total') or 0)
    return {
        'environment': env,
        'balance': str(balance),
        'low_balance_threshold': str(threshold),
        'enforcement_enabled': bool(row.enforcement_enabled),
        'is_low_balance': balance <= threshold,
        'is_negative': balance < 0,
        'last_manual_set_at': row.last_manual_set_at.isoformat() if row.last_manual_set_at else None,
        'updated_by_id': row.updated_by_id,
        'today_auto_debit_total': str(today_spend),
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


@transaction.atomic
def set_float_balance(
    *,
    admin_user,
    new_balance,
    remarks: str,
    environment: str | None = None,
) -> dict[str, Any]:
    env = _env(environment)
    remarks = str(remarks or '').strip()
    if len(remarks) < 5:
        raise ValueError('Remarks are required (at least 5 characters).')
    try:
        new_bal = money_q(Decimal(str(new_balance)))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('new_balance must be a valid number.') from exc
    if new_bal < 0:
        raise ValueError('new_balance cannot be negative.')

    get_or_create_float(env)
    row = BbpsProviderFloat.objects.select_for_update().get(environment=env, is_deleted=False)
    before = money_q(row.balance)
    row.balance = new_bal
    row.updated_by = admin_user
    row.last_manual_set_at = timezone.now()
    row.save(update_fields=['balance', 'updated_by', 'last_manual_set_at', 'updated_at'])

    BbpsProviderFloatLedger.objects.create(
        float_row=row,
        environment=env,
        entry_type='MANUAL_SET',
        amount=abs(new_bal - before),
        balance_before=before,
        balance_after=new_bal,
        service_id='',
        remarks=remarks[:2000],
        performed_by=admin_user,
        performed_by_name=_admin_name(admin_user),
    )
    return get_float_status(env)


@transaction.atomic
def update_float_settings(
    *,
    admin_user=None,
    low_balance_threshold=None,
    enforcement_enabled=None,
    environment: str | None = None,
) -> dict[str, Any]:
    env = _env(environment)
    get_or_create_float(env)
    row = BbpsProviderFloat.objects.select_for_update().get(environment=env, is_deleted=False)
    fields = ['updated_at']
    if low_balance_threshold is not None:
        try:
            row.low_balance_threshold = money_q(Decimal(str(low_balance_threshold)))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError('low_balance_threshold must be a valid number.') from exc
        if row.low_balance_threshold < 0:
            raise ValueError('low_balance_threshold cannot be negative.')
        fields.append('low_balance_threshold')
    if enforcement_enabled is not None:
        row.enforcement_enabled = bool(enforcement_enabled)
        fields.append('enforcement_enabled')
    if admin_user is not None:
        row.updated_by = admin_user
        fields.append('updated_by')
    row.save(update_fields=fields)
    return get_float_status(env)


def check_float_available(amount, *, environment: str | None = None) -> tuple[bool, Decimal]:
    """
    Return (ok, shortfall). When enforcement is off, always ok.
    """
    env = _env(environment)
    try:
        need = money_q(Decimal(str(amount)))
    except (InvalidOperation, TypeError, ValueError):
        need = money_q(Decimal('0'))
    if need <= 0:
        return True, Decimal('0.0000')

    row = get_or_create_float(env)
    if not row.enforcement_enabled:
        return True, Decimal('0.0000')
    bal = money_q(row.balance)
    threshold = money_q(row.low_balance_threshold)
    # If ops has not initialized the tracked float yet, or it has fallen to the
    # alert threshold, stop new BBPS spends until an admin refreshes the figure.
    if row.last_manual_set_at is None:
        return False, need
    if bal <= threshold:
        return False, money_q(max(need, threshold - bal))
    if bal >= need:
        return True, Decimal('0.0000')
    return False, money_q(need - bal)


def assert_float_available(amount, *, environment: str | None = None) -> None:
    ok, shortfall = check_float_available(amount, environment=environment)
    if not ok:
        logger.warning(
            'bbps provider float insufficient env=%s shortfall=%s amount=%s',
            _env(environment),
            shortfall,
            amount,
        )
        raise BbpsProviderFloatInsufficient(shortfall=shortfall)


def _resolve_attempt(service_id: str, payment_attempt: Optional[BbpsPaymentAttempt] = None):
    if payment_attempt is not None:
        return payment_attempt
    sid = str(service_id or '').strip()
    if not sid:
        return None
    return (
        BbpsPaymentAttempt.objects.filter(service_id=sid, is_deleted=False)
        .order_by('-created_at')
        .first()
    )


def debit_float_for_payment(
    service_id: str,
    amount,
    *,
    payment_attempt: Optional[BbpsPaymentAttempt] = None,
    environment: str | None = None,
    remarks: str = '',
) -> Optional[BbpsProviderFloatLedger]:
    """
    Idempotent AUTO_DEBIT for a successful BBPS payment.
    Never raises into the caller — logs and returns None on failure.
    """
    try:
        return _apply_auto_entry(
            entry_type='AUTO_DEBIT',
            service_id=service_id,
            amount=amount,
            payment_attempt=payment_attempt,
            environment=environment,
            remarks=remarks or 'BBPS payment success — provider float debit',
        )
    except Exception:
        logger.exception('provider float AUTO_DEBIT failed service_id=%s', service_id)
        return None


def credit_float_for_refund(
    service_id: str,
    amount,
    *,
    payment_attempt: Optional[BbpsPaymentAttempt] = None,
    environment: str | None = None,
    remarks: str = '',
) -> Optional[BbpsProviderFloatLedger]:
    """Idempotent AUTO_CREDIT for refund/reversal. Never raises into the caller."""
    try:
        return _apply_auto_entry(
            entry_type='AUTO_CREDIT',
            service_id=service_id,
            amount=amount,
            payment_attempt=payment_attempt,
            environment=environment,
            remarks=remarks or 'BBPS payment refund/reversal — provider float credit',
        )
    except Exception:
        logger.exception('provider float AUTO_CREDIT failed service_id=%s', service_id)
        return None


@transaction.atomic
def _apply_auto_entry(
    *,
    entry_type: str,
    service_id: str,
    amount,
    payment_attempt: Optional[BbpsPaymentAttempt],
    environment: str | None,
    remarks: str,
) -> Optional[BbpsProviderFloatLedger]:
    sid = str(service_id or '').strip()
    if not sid:
        logger.warning('provider float %s skipped — empty service_id', entry_type)
        return None
    try:
        amt = money_q(Decimal(str(amount)))
    except (InvalidOperation, TypeError, ValueError):
        logger.warning('provider float %s skipped — invalid amount=%r', entry_type, amount)
        return None
    if amt <= 0:
        return None

    # Already applied (idempotent across sync / poll / webhook).
    existing = BbpsProviderFloatLedger.objects.filter(
        is_deleted=False,
        service_id=sid,
        entry_type=entry_type,
    ).first()
    if existing:
        return existing

    env = _env(environment)
    get_or_create_float(env)
    row = BbpsProviderFloat.objects.select_for_update().get(environment=env, is_deleted=False)
    before = money_q(row.balance)
    if entry_type == 'AUTO_DEBIT':
        after = money_q(before - amt)
    else:
        after = money_q(before + amt)
    row.balance = after
    row.save(update_fields=['balance', 'updated_at'])

    attempt = _resolve_attempt(sid, payment_attempt)
    try:
        entry = BbpsProviderFloatLedger.objects.create(
            float_row=row,
            environment=env,
            entry_type=entry_type,
            amount=amt,
            balance_before=before,
            balance_after=after,
            service_id=sid,
            payment_attempt=attempt,
            remarks=(remarks or '')[:2000],
            performed_by=None,
            performed_by_name='system',
        )
    except IntegrityError:
        # Race: another settlement path wrote the same (service_id, entry_type).
        return BbpsProviderFloatLedger.objects.filter(
            is_deleted=False, service_id=sid, entry_type=entry_type
        ).first()
    return entry


def serialize_ledger_entry(entry: BbpsProviderFloatLedger) -> dict[str, Any]:
    return {
        'id': entry.id,
        'environment': entry.environment,
        'entry_type': entry.entry_type,
        'amount': str(money_q(entry.amount)),
        'balance_before': str(money_q(entry.balance_before)),
        'balance_after': str(money_q(entry.balance_after)),
        'service_id': entry.service_id or '',
        'payment_attempt_id': entry.payment_attempt_id,
        'remarks': entry.remarks or '',
        'performed_by': {
            'id': entry.performed_by_id,
            'name': entry.performed_by_name or '',
        },
        'created_at': entry.created_at.isoformat() if entry.created_at else None,
    }


def list_ledger(
    *,
    environment: str | None = None,
    entry_type: str = '',
    date_from=None,
    date_to=None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    env = _env(environment)
    qs = BbpsProviderFloatLedger.objects.filter(is_deleted=False, environment=env).order_by('-created_at')
    if entry_type:
        qs = qs.filter(entry_type=entry_type.strip().upper())
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 50)))
    total = qs.count()
    start = (page - 1) * page_size
    rows = [serialize_ledger_entry(e) for e in qs[start : start + page_size]]
    return {
        'results': rows,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': (total + page_size - 1) // page_size if page_size else 1,
        },
    }
