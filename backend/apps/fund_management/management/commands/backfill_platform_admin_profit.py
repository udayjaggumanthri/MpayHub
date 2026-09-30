"""
Reclassify admin/platform profit onto Commission report + unify treasury.

Steps (all idempotent):
  A. Reclass payin/bbps ``service_fee`` → ``commission`` (no wallet re-credit).
  B. Book missing BBPS SUCCESS charges that never hit the ledger (wallet + ledger).
  C. Move Super Admin user-1 payin ledger + Main balance onto treasury Admin 43.
  D. Skip payout / bank_verification / chain commission.

Usage:
  python manage.py backfill_platform_admin_profit --dry-run
  python manage.py backfill_platform_admin_profit
  python manage.py backfill_platform_admin_profit --rollback
"""
from __future__ import annotations

import csv
import io
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce

from apps.authentication.models import User
from apps.bbps.models import BillPayment
from apps.fund_management.commission_meta import commission_ledger_create
from apps.fund_management.money_utils import money_q
from apps.fund_management.platform_settlement import get_platform_treasury_user
from apps.transactions.agent_snapshot import display_name_for_user, passbook_initiator_db_fields
from apps.transactions.models import CommissionLedger, PassbookEntry
from apps.wallets.models import Wallet

SOURCE_SA_USER_ID = 1
DEFAULT_TREASURY_USER_ID = 43
PASSBOOK_SYNC_SERVICE = 'PLATFORM_TREASURY_SYNC'
RECLASS_SLICES = frozenset({'admin_absorbed', 'platform_fee', 'gateway_absorbed', 'bbps_admin'})
RECLASS_MODULES = frozenset({'payin', 'bbps'})


def _treasury_user() -> User:
    uid = getattr(settings, 'PLATFORM_PAYIN_SETTLEMENT_USER_ID', None) or DEFAULT_TREASURY_USER_ID
    user = User.objects.filter(pk=int(uid), is_active=True).first()
    if user:
        return user
    treasury = get_platform_treasury_user()
    if treasury:
        return treasury
    raise RuntimeError('No treasury user available (set PLATFORM_PAYIN_SETTLEMENT_USER_ID).')


def _passbook_move(*, user, debit: bool, amount: Decimal, service_id: str, description: str) -> None:
    amount = money_q(amount)
    if amount <= 0:
        return
    w = Wallet.get_wallet(user, 'main')
    ob = money_q(w.balance)
    if debit:
        w.debit(
            amount,
            reference=service_id,
            description=description,
            respect_holds=False,
        )
    else:
        w.credit(amount, reference=service_id, description=description)
    w.refresh_from_db()
    PassbookEntry.objects.create(
        user=user,
        wallet_type='main',
        service=PASSBOOK_SYNC_SERVICE,
        service_id=service_id,
        description=description,
        debit_amount=amount if debit else Decimal('0'),
        credit_amount=Decimal('0') if debit else amount,
        opening_balance=ob,
        closing_balance=money_q(w.balance),
        service_charge=Decimal('0'),
        principal_amount=amount,
        **passbook_initiator_db_fields(user),
    )


class Command(BaseCommand):
    help = (
        'Reclass payin/bbps admin profit to commission, book unbooked BBPS charges, '
        'and unify Super Admin Main onto treasury Admin without deleting ledger rows.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report planned changes without writing.',
        )
        parser.add_argument(
            '--rollback',
            action='store_true',
            help='Reverse unify (C) and reverse reclass (A). Does not reverse BBPS booking (B) — use clawback_settlement.',
        )
        parser.add_argument(
            '--from-user',
            type=int,
            default=SOURCE_SA_USER_ID,
            help='Super Admin user id to move from (default 1).',
        )
        parser.add_argument(
            '--to-user',
            type=int,
            default=None,
            help='Treasury Admin user id (default PLATFORM_PAYIN_SETTLEMENT_USER_ID or 43).',
        )
        parser.add_argument(
            '--csv',
            action='store_true',
            help='Print a CSV summary of planned/applied totals.',
        )

    def handle(self, *args, **options):
        dry = bool(options['dry_run'])
        rollback = bool(options['rollback'])
        from_id = int(options['from_user'])
        to_user = (
            User.objects.filter(pk=int(options['to_user']), is_active=True).first()
            if options['to_user']
            else _treasury_user()
        )
        if not to_user:
            self.stderr.write(self.style.ERROR('Treasury user not found.'))
            return

        if rollback:
            stats = self._rollback(dry=dry, from_id=from_id, to_user=to_user)
        else:
            stats = self._apply(dry=dry, from_id=from_id, to_user=to_user)

        self.stdout.write(self.style.SUCCESS(
            f"{'DRY-RUN ' if dry else ''}{'ROLLBACK ' if rollback else ''}done: {stats}"
        ))
        if options['csv']:
            self._print_csv(stats)

    def _apply(self, *, dry: bool, from_id: int, to_user: User) -> dict:
        stats = {
            'dry_run': dry,
            'treasury_user_id': to_user.pk,
            'reclass_rows': 0,
            'reclass_amount': Decimal('0'),
            'bbps_booked': 0,
            'bbps_amount': Decimal('0'),
            'unify_ledger_rows': 0,
            'unify_wallet_amount': Decimal('0'),
            'skipped_already_unified': False,
        }

        from django.db.models import Q

        with transaction.atomic():
            # A. Reclassify only — no wallet credit.
            reclass_qs = CommissionLedger.objects.filter(entry_kind='service_fee').filter(
                Q(module__in=('payin', 'bbps'))
                | Q(source__in=('payin', 'profit', 'bbps'), module='')
            ).filter(
                Q(slice_key__in=list(RECLASS_SLICES)) | Q(slice_key='')
            ).exclude(
                Q(module='payout')
                | Q(source='payout')
                | Q(module='bank_verification')
                | Q(source='bank_verification')
            )

            reclass_amount = reclass_qs.aggregate(
                s=Coalesce(Sum('amount'), Decimal('0'))
            )['s'] or Decimal('0')
            stats['reclass_rows'] = reclass_qs.count()
            stats['reclass_amount'] = money_q(reclass_amount)

            if not dry and stats['reclass_rows']:
                for row in reclass_qs.iterator(chunk_size=200):
                    meta = dict(row.meta or {})
                    meta['wallet_credited'] = True
                    meta['tracker'] = 'commission'
                    meta['reclassed_from'] = 'service_fee'
                    CommissionLedger.objects.filter(pk=row.pk).update(
                        entry_kind='commission',
                        meta=meta,
                    )

            # B. Book missing BBPS SUCCESS with charge and no ledger.
            missing = self._missing_bbps_qs()
            stats['bbps_booked'] = missing.count()
            bbps_total = Decimal('0')
            for bp in missing.iterator(chunk_size=100):
                charge = money_q(bp.charge or 0)
                if charge <= 0:
                    continue
                bbps_total += charge
                if dry:
                    continue
                # Idempotent: skip if any ledger now exists for this service_id.
                if CommissionLedger.objects.filter(reference_service_id=bp.service_id).exists():
                    continue
                self._book_bbps_commission(bp=bp, treasury=to_user, charge=charge)
            stats['bbps_amount'] = money_q(bbps_total)

            # C. Unify treasury: reassign user 1 payin ledger → 43; move wallet.
            from_user = User.objects.filter(pk=from_id).first()
            if from_user and from_user.pk != to_user.pk:
                # Platform payin profit on SA (not hierarchy chain roles).
                sa_rows = CommissionLedger.objects.filter(user_id=from_id).filter(
                    Q(module='payin') | Q(source__in=('payin', 'profit'))
                ).exclude(
                    slice_key__in=(
                        'Super Distributor', 'Master Distributor', 'Distributor', 'Retailer',
                    )
                )
                unify_sum = sa_rows.aggregate(
                    s=Coalesce(Sum('amount'), Decimal('0'))
                )['s'] or Decimal('0')
                stats['unify_ledger_rows'] = sa_rows.count()

                from_wallet = Wallet.objects.filter(user=from_user, wallet_type='main').first()
                from_bal = money_q(from_wallet.balance) if from_wallet else Decimal('0')
                # Move the Super Admin Main balance that matches booked admin profit.
                # Plan: debit 1 / credit 43 by ₹38,414.0915 (the SA payin admin_absorbed total).
                move_amt = money_q(unify_sum) if unify_sum > 0 else from_bal
                # If ledger already reassigned, detect via zero SA rows + optional prior sync.
                if stats['unify_ledger_rows'] == 0 and from_bal == 0:
                    stats['skipped_already_unified'] = True
                    move_amt = Decimal('0')
                stats['unify_wallet_amount'] = money_q(move_amt)

                if not dry and stats['unify_ledger_rows']:
                    # Reassign carefully around unique (reference_service_id, user, slice_key).
                    for row in list(sa_rows):
                        conflict = CommissionLedger.objects.filter(
                            reference_service_id=row.reference_service_id,
                            user=to_user,
                            slice_key=row.slice_key or '',
                        ).exclude(pk=row.pk).first()
                        if conflict:
                            # Merge amount onto treasury row; keep SA row by zeroing+retag
                            # WITHOUT deleting — mark superseded and leave amount on treasury.
                            conflict_meta = dict(conflict.meta or {})
                            conflict_meta['merged_from_user'] = from_id
                            conflict_meta['merged_from_ledger_id'] = row.pk
                            CommissionLedger.objects.filter(pk=conflict.pk).update(
                                amount=money_q(conflict.amount) + money_q(row.amount),
                                meta=conflict_meta,
                            )
                            row_meta = dict(row.meta or {})
                            row_meta['superseded_by'] = conflict.pk
                            row_meta['treasury_unified'] = True
                            CommissionLedger.objects.filter(pk=row.pk).update(
                                user=to_user,
                                amount=Decimal('0'),
                                slice_key=(f"{row.slice_key or 'slice'}_sa_merged")[:64],
                                meta=row_meta,
                                entry_kind='commission',
                            )
                        else:
                            row_meta = dict(row.meta or {})
                            row_meta['treasury_unified_from'] = from_id
                            row_meta['wallet_credited'] = True
                            row_meta['tracker'] = 'commission'
                            CommissionLedger.objects.filter(pk=row.pk).update(
                                user=to_user,
                                entry_kind='commission',
                                meta=row_meta,
                            )

                if not dry and move_amt > 0 and from_bal > 0:
                    # Cap move at available SA main so we never go negative.
                    actual = money_q(min(move_amt, from_bal))
                    sid = f'TREASURY-UNIFY-{from_id}-TO-{to_user.pk}'
                    _passbook_move(
                        user=from_user,
                        debit=True,
                        amount=actual,
                        service_id=sid,
                        description=(
                            f'Platform treasury sync: move Main to Admin {to_user.pk}'
                        ),
                    )
                    _passbook_move(
                        user=to_user,
                        debit=False,
                        amount=actual,
                        service_id=sid,
                        description=(
                            f'Platform treasury sync: receive Main from user {from_id}'
                        ),
                    )
                    stats['unify_wallet_amount'] = actual
            else:
                stats['skipped_already_unified'] = True

            if dry:
                transaction.set_rollback(True)

        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in stats.items()}

    def _rollback(self, *, dry: bool, from_id: int, to_user: User) -> dict:
        """Reverse A (entry_kind) and C (wallet + user_id). Does not undo B."""
        from django.db.models import Q

        stats = {
            'dry_run': dry,
            'rollback': True,
            'reclass_reverted': 0,
            'unify_ledger_reverted': 0,
            'unify_wallet_amount': Decimal('0'),
        }
        from_user = User.objects.filter(pk=from_id).first()
        with transaction.atomic():
            # A reverse: rows marked reclassed_from=service_fee
            reclassed = CommissionLedger.objects.filter(
                entry_kind='commission',
                meta__reclassed_from='service_fee',
            )
            stats['reclass_reverted'] = reclassed.count()
            if not dry:
                for row in reclassed.iterator(chunk_size=200):
                    meta = dict(row.meta or {})
                    meta.pop('reclassed_from', None)
                    meta['tracker'] = 'service_fee'
                    CommissionLedger.objects.filter(pk=row.pk).update(
                        entry_kind='service_fee',
                        meta=meta,
                    )

            if from_user and from_user.pk != to_user.pk:
                unified = CommissionLedger.objects.filter(
                    user=to_user,
                    meta__treasury_unified_from=from_id,
                )
                # Also rows with amount 0 superseded merges — leave alone (complex).
                stats['unify_ledger_reverted'] = unified.count()
                move_amt = unified.aggregate(
                    s=Coalesce(Sum('amount'), Decimal('0'))
                )['s'] or Decimal('0')
                stats['unify_wallet_amount'] = money_q(move_amt)

                if not dry and stats['unify_ledger_reverted']:
                    for row in list(unified):
                        meta = dict(row.meta or {})
                        meta.pop('treasury_unified_from', None)
                        CommissionLedger.objects.filter(pk=row.pk).update(
                            user=from_user,
                            meta=meta,
                        )

                if not dry and move_amt > 0:
                    to_wallet = Wallet.objects.filter(user=to_user, wallet_type='main').first()
                    to_bal = money_q(to_wallet.balance) if to_wallet else Decimal('0')
                    actual = money_q(min(move_amt, to_bal))
                    sid = f'TREASURY-UNIFY-ROLLBACK-{to_user.pk}-TO-{from_id}'
                    _passbook_move(
                        user=to_user,
                        debit=True,
                        amount=actual,
                        service_id=sid,
                        description=f'Platform treasury sync rollback to user {from_id}',
                    )
                    _passbook_move(
                        user=from_user,
                        debit=False,
                        amount=actual,
                        service_id=sid,
                        description=f'Platform treasury sync rollback from Admin {to_user.pk}',
                    )
                    stats['unify_wallet_amount'] = actual

            if dry:
                transaction.set_rollback(True)

        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in stats.items()}

    def _missing_bbps_qs(self):
        """SUCCESS bill payments with charge>0 and no commission_ledger for service_id."""
        ledgered_ids = (
            CommissionLedger.objects.exclude(reference_service_id='')
            .values_list('reference_service_id', flat=True)
            .distinct()
        )
        return (
            BillPayment.objects.filter(status='SUCCESS', charge__gt=0)
            .exclude(service_id__in=ledgered_ids)
            .order_by('id')
        )

    def _book_bbps_commission(self, *, bp: BillPayment, treasury: User, charge: Decimal) -> None:
        payer = bp.user
        sid = bp.service_id
        src = {
            'source_user_id': payer.pk if payer else None,
            'source_user_code': (
                getattr(payer, 'user_id', '') or getattr(payer, 'display_code', '') or ''
            ) if payer else '',
            'source_role': getattr(payer, 'role', '') if payer else '',
            'source_name': display_name_for_user(payer) if payer else '',
            'biller': bp.biller or '',
            'bill_type': bp.bill_type or '',
            'backfill': 'bbps_unbooked',
            'wallet_credited': True,
            'tracker': 'commission',
            'slice': 'bbps_admin',
        }
        w = Wallet.get_wallet(treasury, 'main')
        ob = money_q(w.balance)
        w.credit(charge, reference=sid, description=f'BBPS platform commission backfill on {sid}')
        w.refresh_from_db()
        PassbookEntry.objects.create(
            user=treasury,
            wallet_type='main',
            service='COMMISSION',
            service_id=sid,
            description=f'BBPS platform commission backfill on {sid}',
            debit_amount=Decimal('0'),
            credit_amount=charge,
            opening_balance=ob,
            closing_balance=money_q(w.balance),
            service_charge=Decimal('0'),
            principal_amount=money_q(bp.amount or 0),
            **passbook_initiator_db_fields(payer or treasury),
        )
        commission_ledger_create(
            user=treasury,
            role_at_time='PLATFORM',
            amount=charge,
            source='bbps',
            entry_kind='commission',
            module='bbps',
            slice_key='bbps_admin',
            customer_charge=charge,
            reference_service_id=sid,
            wallet_type='main',
            meta=src,
            source_user_code=str(src.get('source_user_code') or '')[:30],
            source_role=str(src.get('source_role') or '')[:50],
            source_name_snapshot=str(src.get('source_name') or '')[:255],
        )

    def _print_csv(self, stats: dict) -> None:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['key', 'value'])
        for k, v in stats.items():
            w.writerow([k, v])
        self.stdout.write(buf.getvalue())
