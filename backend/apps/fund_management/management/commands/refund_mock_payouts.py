"""
Refund allowlisted SUCCESS payouts that settled from mock/UAT provider responses
(no real bank credit). Restores agent Main, claws back platform fee/commission
ledger (and treasury Main where wallet was credited). Compensating entries only.

Usage:
  python manage.py refund_mock_payouts --dry-run
  python manage.py refund_mock_payouts --execute --confirm REFUND-MOCK-PAYOUTS
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.fund_management.models import Payout, PayoutProviderEvent
from apps.fund_management.money_utils import money_q
from apps.transactions.agent_snapshot import passbook_initiator_db_fields
from apps.transactions.models import CommissionLedger, PassbookEntry, Transaction
from apps.transactions.services.fee_settlement import clawback_settlement
from apps.wallets.models import Wallet

logger = logging.getLogger(__name__)

# Hard allowlist — only these live mock SUCCESS payouts.
ALLOWLIST_TXN_IDS = (
    'PMPO2026100131156',
    'PMPO2026093001954',
)

CONFIRM_TOKEN = 'REFUND-MOCK-PAYOUTS'
FAILURE_REASON = 'Refunded: mock/UAT provider SUCCESS without bank credit'
REFUND_META_KEY = 'admin_refund'


def _already_refunded(payout: Payout) -> bool:
    meta = payout.response_meta if isinstance(payout.response_meta, dict) else {}
    if isinstance(meta.get(REFUND_META_KEY), dict):
        return True
    if payout.status == 'FAILED' and FAILURE_REASON in (payout.failure_reason or ''):
        return True
    return False


def preview_refund(payout: Payout) -> dict[str, Any]:
    """Read-only summary of what refund would do."""
    tid = payout.transaction_id
    agent = payout.user
    agent_w = Wallet.get_wallet(agent, 'main')
    ledgers = list(
        CommissionLedger.objects.filter(reference_service_id=tid)
        .exclude(slice_key__endswith='_reversal')
        .filter(amount__gt=0)
        .order_by('id')
    )
    clawback_wallet = Decimal('0')
    clawback_tracker = Decimal('0')
    ledger_preview = []
    for row in ledgers:
        meta = row.meta if isinstance(row.meta, dict) else {}
        credited = meta.get('wallet_credited')
        if credited is None:
            credited = True
        amt = money_q(row.amount)
        if credited:
            clawback_wallet += amt
        else:
            clawback_tracker += amt
        ledger_preview.append(
            {
                'id': row.id,
                'user_id': row.user_id,
                'slice_key': row.slice_key,
                'entry_kind': row.entry_kind,
                'amount': str(amt),
                'wallet_credited': bool(credited),
            }
        )
    return {
        'transaction_id': tid,
        'status': payout.status,
        'already_refunded': _already_refunded(payout),
        'agent_user_id': agent.pk,
        'agent_code': getattr(agent, 'display_code', None) or getattr(agent, 'user_id', ''),
        'amount': str(money_q(payout.amount)),
        'charge': str(money_q(payout.charge)),
        'total_deducted': str(money_q(payout.total_deducted)),
        'agent_main_before': str(money_q(agent_w.balance)),
        'agent_main_after_if_execute': str(money_q(agent_w.balance) + money_q(payout.total_deducted)),
        'clawback_wallet_debit_total': str(money_q(clawback_wallet)),
        'clawback_tracker_only_total': str(money_q(clawback_tracker)),
        'ledgers': ledger_preview,
    }


@db_transaction.atomic
def refund_one_mock_payout(*, payout: Payout, dry_run: bool = True) -> dict[str, Any]:
    """
    Reverse one SUCCESS allowlisted payout. Idempotent.
    Returns a result dict. Raises on unexpected state when executing.
    """
    locked = (
        Payout.objects.select_for_update()
        .select_related('user')
        .get(pk=payout.pk)
    )
    tid = locked.transaction_id
    preview = preview_refund(locked)

    if _already_refunded(locked):
        preview['action'] = 'skipped_already_refunded'
        return preview

    if locked.status != 'SUCCESS':
        preview['action'] = 'skipped_not_success'
        preview['error'] = f'Expected SUCCESS, got {locked.status}'
        return preview

    if dry_run:
        preview['action'] = 'dry_run'
        return preview

    # 1) Claw back platform fee/commission settlement
    clawed = clawback_settlement(service_id=tid, reason='mock_payout_refund')
    clawback_ids = [r.pk for r in clawed]

    # 2) Credit agent Main for full total_deducted
    agent = locked.user
    refund_amt = money_q(locked.total_deducted)
    if refund_amt <= 0:
        raise CommandError(f'{tid}: total_deducted is not positive')

    wallet = Wallet.get_wallet(agent, 'main')
    opening = money_q(wallet.balance)
    wallet.credit(
        refund_amt,
        reference=f'{tid}:refund',
        description=f'Payout refund {tid} (mock provider)',
    )
    wallet.refresh_from_db()
    closing = money_q(wallet.balance)

    PassbookEntry.objects.create(
        user=agent,
        wallet_type='main',
        service='PAYOUT REFUND',
        service_id=tid,
        description=(
            f'REFUND PAYOUT {locked.transfer_mode}, '
            f'AMOUNT ₹{money_q(locked.amount)}, charge ₹{money_q(locked.charge)} '
            f'(mock/UAT success reversed)'
        ),
        debit_amount=Decimal('0'),
        credit_amount=refund_amt,
        opening_balance=opening,
        closing_balance=closing,
        service_charge=money_q(locked.charge),
        principal_amount=money_q(locked.amount),
        **passbook_initiator_db_fields(agent),
    )

    # 3) Mark payout FAILED
    meta = dict(locked.response_meta) if isinstance(locked.response_meta, dict) else {}
    meta[REFUND_META_KEY] = {
        'at': timezone.now().isoformat(),
        'reason': FAILURE_REASON,
        'total_refunded': str(refund_amt),
        'clawback_ledger_ids': clawback_ids,
        'agent_opening': str(opening),
        'agent_closing': str(closing),
    }
    locked.response_meta = meta
    locked.status = 'FAILED'
    locked.failure_reason = FAILURE_REASON[:2000]
    locked.save(update_fields=['status', 'failure_reason', 'response_meta', 'updated_at'])

    # 4) Related Transaction → FAILED
    Transaction.objects.filter(service_id=tid, transaction_type='payout').update(status='FAILED')

    # 5) Audit event
    try:
        PayoutProviderEvent.objects.create(
            payout=locked,
            provider_code=locked.provider_code or 'vimopay',
            direction='inbound',
            event_type='admin_refund',
            merchant_ref_id=tid,
            payload={
                'total_refunded': str(refund_amt),
                'clawback_ledger_ids': clawback_ids,
                'reason': FAILURE_REASON,
            },
            notes=FAILURE_REASON[:500],
        )
    except Exception:
        logger.exception('Failed to write PayoutProviderEvent for refund %s', tid)

    preview['action'] = 'refunded'
    preview['agent_main_after'] = str(closing)
    preview['clawback_ledger_ids'] = clawback_ids
    return preview


class Command(BaseCommand):
    help = (
        'Refund allowlisted mock SUCCESS payouts: restore agent Main, clawback '
        'platform fee/commission, mark FAILED. Default is dry-run.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview only (default if --execute not passed)',
        )
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Apply refunds (requires --confirm)',
        )
        parser.add_argument(
            '--confirm',
            type=str,
            default='',
            help=f'Must be exactly {CONFIRM_TOKEN} when using --execute',
        )
        parser.add_argument(
            '--txn',
            action='append',
            dest='txns',
            default=None,
            help='Optional subset of allowlisted txn ids (repeatable)',
        )

    def handle(self, *args, **options):
        execute = bool(options.get('execute'))
        explicit_dry = bool(options.get('dry_run'))

        if execute and explicit_dry:
            self.stdout.write(self.style.WARNING('Both --dry-run and --execute: staying dry-run.'))
            dry_run = True
        elif execute:
            if (options.get('confirm') or '').strip() != CONFIRM_TOKEN:
                raise CommandError(f'--execute requires --confirm {CONFIRM_TOKEN}')
            dry_run = False
        else:
            dry_run = True

        requested = options.get('txns') or list(ALLOWLIST_TXN_IDS)
        for tid in requested:
            if tid not in ALLOWLIST_TXN_IDS:
                raise CommandError(f'{tid} is not in the hard allowlist')

        self.stdout.write(
            f'Mode: {"DRY-RUN" if dry_run else "EXECUTE"} | txns={list(requested)}'
        )

        results = []
        for tid in requested:
            payout = Payout.objects.filter(transaction_id=tid, is_deleted=False).first()
            if not payout:
                self.stderr.write(self.style.ERROR(f'{tid}: not found'))
                results.append({'transaction_id': tid, 'action': 'not_found'})
                continue
            result = refund_one_mock_payout(payout=payout, dry_run=dry_run)
            results.append(result)
            action = result.get('action')
            style = self.style.SUCCESS if action == 'refunded' else self.style.WARNING
            self.stdout.write(style(f'{tid}: {action}'))
            self.stdout.write(
                f"  agent={result.get('agent_code')} "
                f"total={result.get('total_deducted')} "
                f"main {result.get('agent_main_before')} -> "
                f"{result.get('agent_main_after') or result.get('agent_main_after_if_execute')}"
            )
            self.stdout.write(
                f"  clawback wallet={result.get('clawback_wallet_debit_total')} "
                f"tracker_only={result.get('clawback_tracker_only_total')} "
                f"ledgers={result.get('ledgers')}"
            )

        refunded = sum(1 for r in results if r.get('action') == 'refunded')
        skipped = sum(
            1
            for r in results
            if str(r.get('action', '')).startswith('skipped') or r.get('action') == 'dry_run'
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Done. refunded={refunded} preview_or_skipped={skipped} dry_run={dry_run}'
            )
        )
