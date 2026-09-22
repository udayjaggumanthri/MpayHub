"""
CMS wallet operations on the shared Main wallet.

Holds / settles / releases use ``Wallet.hold`` / ``settle_hold`` / ``release``.
``CmsWallet`` / ``CmsWalletEntry`` remain as CMS-specific audit metadata only
(no separate spendable balance).
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction as db_transaction
from rest_framework.exceptions import ValidationError

from apps.cms.models import CmsTransaction, CmsWallet, CmsWalletEntry
from apps.cms.services.ids import generate_cms_tran_id
from apps.core.exceptions import InsufficientBalance
from apps.transactions.models import PassbookEntry
from apps.wallets.models import Wallet

logger = logging.getLogger(__name__)


def _money_q(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal('0.0001'))


def get_or_create_wallet(user) -> CmsWallet:
    """CMS audit row only — balances live on main Wallet."""
    wallet, _ = CmsWallet.objects.get_or_create(
        user=user,
        defaults={'balance': Decimal('0'), 'held_balance': Decimal('0')},
    )
    return wallet


def available_balance(user) -> Decimal:
    main = Wallet.get_wallet(user, 'main')
    return _money_q(main.available_balance)


def wallet_snapshot(user) -> dict:
    main = Wallet.get_wallet(user, 'main')
    bal = _money_q(main.balance)
    held = _money_q(main.held_balance)
    return {
        'balance': str(bal),
        'held_balance': str(held),
        'available': str(bal - held if bal > held else Decimal('0')),
        'source': 'main',
    }


@db_transaction.atomic
def fund_from_main(*, user, amount: Decimal) -> dict:
    """
    Deprecated after single-wallet consolidation.
    CMS debits the main wallet directly — no separate CMS funding step.
    """
    raise ValidationError({
        'code': 'CMS_FUND_REMOVED',
        'message': (
            'CMS funding transfer has been removed. '
            'CMS holds and settlements use your main wallet directly.'
        ),
    })


@db_transaction.atomic
def place_hold(*, user, amount: Decimal, fp_transaction_id: str, bc_login_id: str, meta: dict | None = None) -> CmsTransaction:
    amt = _money_q(amount)
    if amt <= 0:
        raise ValidationError({'message': 'Amount must be greater than zero'})

    existing = CmsTransaction.objects.filter(fp_transaction_id=fp_transaction_id, is_deleted=False).first()
    if existing:
        return existing

    main = Wallet.get_wallet(user, 'main')
    try:
        main.hold(amt, reference=fp_transaction_id, description=f'CMS hold {fp_transaction_id}')
    except InsufficientBalance as exc:
        raise InsufficientBalance(
            f'Insufficient wallet balance. Available: ₹{main.available_balance}, Required: ₹{amt}'
        ) from exc

    from django.utils import timezone
    from apps.cms.models import CmsAgentProfile

    agent = CmsAgentProfile.objects.filter(user=user, is_deleted=False).first()
    mid = generate_cms_tran_id('CMS')
    txn = CmsTransaction.objects.create(
        user=user,
        agent=agent,
        merchant_transaction_id=mid,
        fp_transaction_id=fp_transaction_id,
        amount=amt.quantize(Decimal('0.01')),
        status='initiated',
        bc_login_id=bc_login_id or '',
        provider_meta=meta or {},
        initiated_at=timezone.now(),
    )

    cms = get_or_create_wallet(user)
    CmsWalletEntry.objects.create(
        wallet=cms,
        entry_type='hold',
        amount=amt,
        opening_balance=_money_q(main.balance),
        closing_balance=_money_q(main.balance),
        reference=mid,
        transaction=txn,
        description=f'Hold for {fp_transaction_id} (main wallet)',
    )
    return txn


@db_transaction.atomic
def settle_hold(*, txn: CmsTransaction) -> CmsTransaction:
    if txn.status == 'success':
        return txn
    if txn.status != 'initiated':
        raise ValidationError({'message': f'Cannot settle txn in status {txn.status}'})

    main = Wallet.get_wallet(txn.user, 'main')
    amt = _money_q(txn.amount)
    ob = _money_q(main.balance)
    main.settle_hold(amt, reference=txn.merchant_transaction_id, description=f'CMS settle {txn.fp_transaction_id}')
    main.refresh_from_db()
    cb = _money_q(main.balance)

    PassbookEntry.objects.create(
        user=txn.user,
        wallet_type='main',
        service='CMS',
        service_id=txn.merchant_transaction_id,
        description=f'CMS settlement {txn.fp_transaction_id}',
        debit_amount=amt,
        credit_amount=Decimal('0'),
        opening_balance=ob,
        closing_balance=cb,
        service_charge=Decimal('0'),
        principal_amount=amt,
    )

    from django.utils import timezone

    cms = get_or_create_wallet(txn.user)
    CmsWalletEntry.objects.create(
        wallet=cms,
        entry_type='settle',
        amount=amt,
        opening_balance=ob,
        closing_balance=cb,
        reference=txn.merchant_transaction_id,
        transaction=txn,
        description=f'Settle {txn.fp_transaction_id}',
    )
    txn.status = 'success'
    txn.finalized_at = timezone.now()
    txn.save(update_fields=['status', 'finalized_at', 'updated_at'])
    return txn


@db_transaction.atomic
def release_hold(*, txn: CmsTransaction, status: str = 'failed', error_message: str = '') -> CmsTransaction:
    if txn.status in ('success', 'failed', 'expired'):
        return txn
    if txn.status != 'initiated':
        raise ValidationError({'message': f'Cannot release txn in status {txn.status}'})

    main = Wallet.get_wallet(txn.user, 'main')
    amt = _money_q(txn.amount)
    held = _money_q(main.held_balance)
    release_amt = min(held, amt)

    from django.utils import timezone

    if release_amt > 0:
        main.release(release_amt, reference=txn.merchant_transaction_id, description=f'CMS release {txn.fp_transaction_id}')
        cms = get_or_create_wallet(txn.user)
        CmsWalletEntry.objects.create(
            wallet=cms,
            entry_type='release',
            amount=release_amt,
            opening_balance=_money_q(main.balance),
            closing_balance=_money_q(main.balance),
            reference=txn.merchant_transaction_id,
            transaction=txn,
            description=f'Release {txn.fp_transaction_id}',
        )

    txn.status = status if status in ('failed', 'expired') else 'failed'
    txn.error_message = (error_message or txn.error_message or '')[:500]
    txn.finalized_at = timezone.now()
    txn.save(update_fields=['status', 'error_message', 'finalized_at', 'updated_at'])
    return txn


@db_transaction.atomic
def release_stale_holds(*, older_than_hours: int = 24) -> int:
    from datetime import timedelta

    from django.utils import timezone

    cutoff = timezone.now() - timedelta(hours=max(1, older_than_hours))
    qs = CmsTransaction.objects.filter(
        status='initiated',
        is_deleted=False,
        initiated_at__lt=cutoff,
    )
    count = 0
    for txn in qs.select_related('user'):
        release_hold(txn=txn, status='expired', error_message='Hold expired by sweeper')
        count += 1
    return count
