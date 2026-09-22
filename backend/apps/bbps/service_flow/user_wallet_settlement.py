"""
BBPS user-wallet hold / settle / release / refund on the shared Main wallet.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from apps.core.exceptions import InsufficientBalance
from apps.fund_management.money_utils import money_q
from apps.transactions.agent_snapshot import passbook_initiator_db_fields, transaction_agent_db_fields
from apps.transactions.models import PassbookEntry, Transaction
from apps.wallets.models import Wallet

logger = logging.getLogger(__name__)


def _total_for_attempt(attempt) -> Decimal:
    if attempt.bill_payment_id and attempt.bill_payment is not None:
        return money_q(attempt.bill_payment.total_deducted or 0)
    principal = money_q(Decimal(str(attempt.amount_paise or 0)) / Decimal('100'))
    charge = money_q(attempt.commission_amount or 0)
    return money_q(principal + charge)


def place_payment_hold(*, attempt, amount: Decimal | None = None) -> Decimal:
    """Reserve funds on main wallet for an in-flight BBPS payment."""
    amt = money_q(amount if amount is not None else _total_for_attempt(attempt))
    if amt <= 0:
        return Decimal('0')
    # Already held?
    held = money_q(getattr(attempt, 'wallet_hold_amount', 0) or 0)
    if held > 0:
        return held

    main = Wallet.get_wallet(attempt.user, 'main')
    main.hold(amt, reference=attempt.service_id or attempt.idempotency_key, description='BBPS payment hold')
    attempt.wallet_hold_amount = amt
    attempt.wallet_settled_amount = Decimal('0')
    attempt.save(update_fields=['wallet_hold_amount', 'wallet_settled_amount', 'updated_at'])
    return amt


@db_transaction.atomic
def settle_payment_hold(*, attempt, bill_data: dict | None = None) -> bool:
    """
    Convert hold into a real debit + passbook + Transaction row.
    Idempotent: if already settled, returns False.
    """
    settled = money_q(getattr(attempt, 'wallet_settled_amount', 0) or 0)
    if settled > 0:
        return False

    amt = money_q(getattr(attempt, 'wallet_hold_amount', 0) or 0) or _total_for_attempt(attempt)
    if amt <= 0:
        return False

    user = attempt.user
    main = Wallet.get_wallet(user, 'main')
    bill_payment = attempt.bill_payment
    service_id = (bill_payment.service_id if bill_payment else None) or attempt.service_id
    principal = money_q(bill_payment.amount if bill_payment else (Decimal(str(attempt.amount_paise or 0)) / 100))
    charge = money_q(bill_payment.charge if bill_payment else attempt.commission_amount or 0)
    bill_data = bill_data or {}

    held = money_q(main.held_balance)
    if held >= amt:
        ob = money_q(main.balance)
        main.settle_hold(amt, reference=service_id, description=f'BBPS settle {service_id}')
        main.refresh_from_db()
        cb = money_q(main.balance)
    else:
        # Fallback: direct debit if hold was lost (legacy path / partial state)
        ob = money_q(main.balance)
        if main.available_balance < amt and money_q(main.balance) < amt:
            raise InsufficientBalance(
                f'Insufficient wallet balance to settle BBPS payment. '
                f'Available: ₹{main.available_balance}, Required: ₹{amt}'
            )
        if money_q(main.held_balance) > 0:
            try:
                main.release(min(money_q(main.held_balance), amt), reference=service_id)
            except Exception:
                pass
        main.debit(amt, reference=service_id, description=f'BBPS pay {service_id}')
        main.refresh_from_db()
        cb = money_q(main.balance)

    PassbookEntry.objects.create(
        user=user,
        wallet_type='main',
        service='BBPS',
        service_id=service_id,
        description=(
            f"PAID FOR {bill_data.get('bill_type') or (bill_payment.bill_type if bill_payment else 'BILL')}, "
            f"BILLER: {bill_data.get('biller') or (bill_payment.biller if bill_payment else 'N/A')}, "
            f"AMOUNT: {principal}, CHARGE: {charge}"
        ),
        debit_amount=amt,
        credit_amount=Decimal('0.00'),
        opening_balance=ob,
        closing_balance=cb,
        service_charge=charge,
        principal_amount=principal,
        **passbook_initiator_db_fields(user),
    )

    if not Transaction.objects.filter(service_id=service_id, transaction_type='bbps').exists():
        Transaction.objects.create(
            user=user,
            transaction_type='bbps',
            amount=principal,
            charge=charge,
            status='SUCCESS',
            service_id=service_id,
            request_id=(bill_payment.request_id if bill_payment else attempt.request_id) or None,
            bill_type=bill_data.get('bill_type') or (bill_payment.bill_type if bill_payment else ''),
            biller=bill_data.get('biller') or (bill_payment.biller if bill_payment else ''),
            service_family='bbps',
            **transaction_agent_db_fields(user),
        )

    attempt.wallet_settled_amount = amt
    attempt.wallet_hold_amount = Decimal('0')
    attempt.save(update_fields=['wallet_settled_amount', 'wallet_hold_amount', 'updated_at'])

    if charge > 0:
        try:
            from apps.transactions.services.fee_settlement import settle_service_charge

            settle_service_charge(
                payer=user,
                module='bbps',
                service_id=service_id,
                charge=charge,
                principal=principal,
                meta={
                    'biller': bill_data.get('biller') or (bill_payment.biller if bill_payment else ''),
                    'bill_type': bill_data.get('bill_type') or (bill_payment.bill_type if bill_payment else ''),
                },
            )
        except Exception:
            logger.exception('BBPS fee settlement failed for %s', service_id)

    return True


@db_transaction.atomic
def release_payment_hold(*, attempt, reason: str = '') -> bool:
    """Release an unreleased hold (FAILED / expired)."""
    held = money_q(getattr(attempt, 'wallet_hold_amount', 0) or 0)
    if held <= 0:
        return False
    if money_q(getattr(attempt, 'wallet_settled_amount', 0) or 0) > 0:
        return False

    main = Wallet.get_wallet(attempt.user, 'main')
    release_amt = min(held, money_q(main.held_balance))
    if release_amt > 0:
        main.release(
            release_amt,
            reference=attempt.service_id or attempt.idempotency_key,
            description=f'BBPS release hold ({reason or "failed"})',
        )
    attempt.wallet_hold_amount = Decimal('0')
    attempt.save(update_fields=['wallet_hold_amount', 'updated_at'])
    return True


@db_transaction.atomic
def refund_settled_payment(*, attempt, reason: str = 'refund') -> bool:
    """
    Credit the user back for a previously settled BBPS payment and claw back fees.
    """
    settled = money_q(getattr(attempt, 'wallet_settled_amount', 0) or 0)
    if settled <= 0:
        # Maybe only held — just release
        return release_payment_hold(attempt=attempt, reason=reason)

    user = attempt.user
    main = Wallet.get_wallet(user, 'main')
    service_id = attempt.service_id or (
        attempt.bill_payment.service_id if attempt.bill_payment_id else ''
    )
    ob = money_q(main.balance)
    main.credit(settled, reference=f'{service_id}:refund', description=f'BBPS {reason} {service_id}')
    main.refresh_from_db()
    PassbookEntry.objects.create(
        user=user,
        wallet_type='main',
        service='BBPS REFUND',
        service_id=service_id,
        description=f'BBPS {reason} credit for {service_id}',
        debit_amount=Decimal('0'),
        credit_amount=settled,
        opening_balance=ob,
        closing_balance=money_q(main.balance),
        service_charge=Decimal('0'),
        principal_amount=settled,
        **passbook_initiator_db_fields(user),
    )
    attempt.wallet_settled_amount = Decimal('0')
    attempt.save(update_fields=['wallet_settled_amount', 'updated_at'])

    try:
        from apps.transactions.services.fee_settlement import clawback_settlement

        clawback_settlement(service_id=service_id, reason=reason)
    except Exception:
        logger.exception('BBPS fee clawback failed for %s', service_id)

    return True


def release_stale_bbps_holds(*, older_than_hours: int = 48) -> int:
    """Release holds on AWAITED/PAY_INITIATED attempts older than N hours."""
    from datetime import timedelta

    from apps.bbps.models import BbpsPaymentAttempt

    cutoff = timezone.now() - timedelta(hours=max(1, older_than_hours))
    qs = BbpsPaymentAttempt.objects.filter(
        status__in=('AWAITED', 'PAY_INITIATED'),
        is_deleted=False,
        wallet_hold_amount__gt=0,
        created_at__lt=cutoff,
    ).select_related('user', 'bill_payment')
    count = 0
    for attempt in qs:
        if release_payment_hold(attempt=attempt, reason='stale_hold_sweeper'):
            attempt.status = 'FAILED'
            attempt.last_error_message = 'Hold expired by sweeper'
            attempt.settled_at = timezone.now()
            attempt.save(update_fields=['status', 'last_error_message', 'settled_at', 'updated_at'])
            if attempt.bill_payment_id:
                attempt.bill_payment.status = 'FAILED'
                attempt.bill_payment.failure_reason = 'Hold expired by sweeper'
                attempt.bill_payment.save(update_fields=['status', 'failure_reason'])
            count += 1
    return count
