"""
Wallet transfer operations (atomic balance + passbook).
"""
import logging
from decimal import Decimal

from django.db import transaction as db_transaction

from apps.transactions.models import PassbookEntry
from apps.wallets.models import Wallet
from apps.core.utils import generate_service_id

logger = logging.getLogger(__name__)


def _money_q(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal('0.0001'))


@db_transaction.atomic
def transfer_main_to_bbps(user, amount: Decimal) -> dict:
    """
    Move funds from main wallet to BBPS wallet. Caller must verify MPIN and financial_tx permission.
    Returns service_id and quantized amount.
    """
    amt = _money_q(amount)
    if amt <= 0:
        raise ValueError('Amount must be greater than zero')

    main = Wallet.get_wallet(user, 'main')
    bbps = Wallet.get_wallet(user, 'bbps')

    service_id = generate_service_id('wallet_transfer')
    ref = service_id

    ob_main = _money_q(main.balance)
    main.debit(amt, reference=ref, description=f'Transfer to BBPS wallet ({service_id})')
    main.refresh_from_db()
    cb_main = _money_q(main.balance)
    PassbookEntry.objects.create(
        user=user,
        wallet_type='main',
        service='WALLET_TRANSFER',
        service_id=service_id,
        description=f'Transfer to BBPS wallet (ref {service_id})',
        debit_amount=amt,
        credit_amount=Decimal('0'),
        opening_balance=ob_main,
        closing_balance=cb_main,
        service_charge=Decimal('0'),
        principal_amount=amt,
    )

    ob_bbps = _money_q(bbps.balance)
    bbps.credit(amt, reference=ref, description=f'Credit from main wallet ({service_id})')
    bbps.refresh_from_db()
    cb_bbps = _money_q(bbps.balance)
    PassbookEntry.objects.create(
        user=user,
        wallet_type='bbps',
        service='WALLET_TRANSFER',
        service_id=service_id,
        description=f'Credit from main wallet (ref {service_id})',
        debit_amount=Decimal('0'),
        credit_amount=amt,
        opening_balance=ob_bbps,
        closing_balance=cb_bbps,
        service_charge=Decimal('0'),
        principal_amount=amt,
    )

    logger.info(
        'main to bbps transfer',
        extra={
            'event': 'wallet_transfer_main_to_bbps',
            'user_id': user.pk,
            'transaction_id': service_id,
            'service_id': service_id,
            'amount': str(amt),
            'status': 'SUCCESS',
        },
    )
    return {'service_id': service_id, 'amount': str(amt)}
