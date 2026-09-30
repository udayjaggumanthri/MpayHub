"""
Remove payout / bank-verification gateway fees from treasury Main wallet.

These charges are paid to external gateways — they belong on Service Fee Tracker
only and must not inflate Admin Main (platform profit).

Usage:
  python manage.py scrub_gateway_fees_from_treasury --dry-run
  python manage.py scrub_gateway_fees_from_treasury
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.fund_management.money_utils import money_q
from apps.fund_management.platform_settlement import get_platform_treasury_user
from apps.transactions.agent_snapshot import passbook_initiator_db_fields
from apps.transactions.models import CommissionLedger, PassbookEntry
from apps.transactions.services.fee_settlement import GATEWAY_FEE_MODULES
from apps.wallets.models import Wallet

PASSBOOK_SERVICE = 'GATEWAY_FEE_SCRUB'
META_FLAG = 'removed_from_treasury'


class Command(BaseCommand):
    help = (
        'Debit treasury Main for historical payout/bank-verification service fees '
        'that were wrongly credited; keep ledger rows as tracker-only.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--treasury-user',
            type=int,
            default=None,
            help='Treasury user pk (default: platform treasury / PLATFORM_PAYIN_SETTLEMENT_USER_ID)',
        )

    def handle(self, *args, **options):
        dry = bool(options['dry_run'])
        treasury = None
        if options['treasury_user']:
            from apps.authentication.models import User
            treasury = User.objects.filter(pk=int(options['treasury_user']), is_active=True).first()
        if treasury is None:
            treasury = get_platform_treasury_user()
        if treasury is None:
            self.stderr.write(self.style.ERROR('No treasury user found.'))
            return

        rows = list(
            CommissionLedger.objects.filter(entry_kind='service_fee')
            .filter(module__in=list(GATEWAY_FEE_MODULES))
            .order_by('id')
        )
        # Also catch source-only rows if module blank.
        extra = list(
            CommissionLedger.objects.filter(entry_kind='service_fee')
            .filter(source__in=list(GATEWAY_FEE_MODULES))
            .exclude(pk__in=[r.pk for r in rows])
            .order_by('id')
        )
        rows.extend(extra)

        stats = {
            'dry_run': dry,
            'treasury_user_id': treasury.pk,
            'rows_seen': len(rows),
            'rows_scrubbed': 0,
            'amount_debited': Decimal('0'),
            'skipped_already': 0,
        }

        with transaction.atomic():
            for row in rows:
                meta = dict(row.meta or {})
                if meta.get(META_FLAG):
                    stats['skipped_already'] += 1
                    continue
                # Already marked tracker-only with explicit false and no wallet user credit
                # still debit if historical REVENUE credit exists on treasury for this sid.
                amt = money_q(row.amount or 0)
                if amt <= 0:
                    stats['skipped_already'] += 1
                    continue

                sid = row.reference_service_id or f'ledger-{row.pk}'
                already_scrubbed = PassbookEntry.objects.filter(
                    user=treasury,
                    service=PASSBOOK_SERVICE,
                    service_id=sid,
                ).exists()
                if already_scrubbed:
                    if not meta.get(META_FLAG):
                        meta[META_FLAG] = True
                        meta['wallet_credited'] = False
                        meta['tracker'] = 'service_fee'
                        if not dry:
                            CommissionLedger.objects.filter(pk=row.pk).update(meta=meta)
                    stats['skipped_already'] += 1
                    continue

                # Was this amount credited onto treasury (or the ledger user)?
                credit_user = row.user or treasury
                had_credit = PassbookEntry.objects.filter(
                    user=credit_user,
                    service_id=sid,
                    credit_amount__gt=0,
                ).exclude(service=PASSBOOK_SERVICE).exists()
                # Also: missing wallet_credited on old rows that sat on operator main
                # (audit: payout/bank fees are inside Admin 43 main).
                needs_debit = had_credit or meta.get('wallet_credited') in (True, None)

                if not needs_debit:
                    meta['wallet_credited'] = False
                    meta['tracker'] = 'service_fee'
                    meta[META_FLAG] = True
                    if not dry:
                        CommissionLedger.objects.filter(pk=row.pk).update(meta=meta)
                    stats['skipped_already'] += 1
                    continue

                if not dry:
                    # Always remove from treasury Main (canonical profit wallet).
                    w = Wallet.get_wallet(treasury, 'main')
                    ob = money_q(w.balance)
                    w.debit(
                        amt,
                        reference=sid,
                        description=(
                            f'Remove {row.module or row.source} gateway fee from treasury '
                            f'(tracker only) on {sid}'
                        ),
                        respect_holds=False,
                    )
                    w.refresh_from_db()
                    PassbookEntry.objects.create(
                        user=treasury,
                        wallet_type='main',
                        service=PASSBOOK_SERVICE,
                        service_id=sid,
                        description=(
                            f'Gateway fee scrub: {row.module or row.source} ₹{amt} '
                            f'is tracker-only (not platform profit) on {sid}'
                        ),
                        debit_amount=amt,
                        credit_amount=Decimal('0'),
                        opening_balance=ob,
                        closing_balance=money_q(w.balance),
                        service_charge=Decimal('0'),
                        principal_amount=amt,
                        **passbook_initiator_db_fields(treasury),
                    )
                    meta['wallet_credited'] = False
                    meta['tracker'] = 'service_fee'
                    meta[META_FLAG] = True
                    meta['scrubbed_amount'] = str(amt)
                    CommissionLedger.objects.filter(pk=row.pk).update(meta=meta)

                stats['rows_scrubbed'] += 1
                stats['amount_debited'] = money_q(stats['amount_debited'] + amt)

            if dry:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"{'DRY-RUN ' if dry else ''}done: { {k: (str(v) if isinstance(v, Decimal) else v) for k, v in stats.items()} }"
        ))
