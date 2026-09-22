"""
Who receives pay-in / service-fee **platform** amounts on the Main wallet.

Admin and Super Admin accounts are login identities for the same platform
treasury — they must not each hold a separate fee wallet or see different
commission totals. Settlement always credits one treasury user; every
operator login reads that same wallet and ledger.
"""
import logging
from decimal import Decimal
from typing import List, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum

from apps.authentication.models import User
from apps.core.roles import OPERATOR_ROLES, is_platform_operator
from apps.fund_management.money_utils import money_q
from apps.fund_management.payin_hierarchy import upline_chain

logger = logging.getLogger(__name__)


def platform_operator_user_ids() -> list[int]:
    """Active Admin / Super Admin PKs (login accounts, not separate money owners)."""
    return list(
        User.objects.filter(is_active=True, role__in=list(OPERATOR_ROLES))
        .order_by('id')
        .values_list('id', flat=True)
    )


def get_platform_treasury_user(payer_user: Optional[User] = None) -> Optional[User]:
    """
    Canonical wallet + CommissionLedger owner for all platform operator logins.

    Resolution order matches ``resolve_platform_payin_recipients`` (single user).
    """
    recipients = resolve_platform_payin_recipients(payer_user)
    return recipients[0] if recipients else None


def ledger_user_for_viewer(viewer: User) -> User:
    """
    Commission / revenue report owner for the logged-in user.

    Platform operators (Admin / Super Admin) always see the shared treasury
    ledger so every login shows the same numbers.
    """
    if viewer and is_platform_operator(viewer):
        treasury = get_platform_treasury_user()
        if treasury:
            return treasury
    return viewer


def wallet_user_for_viewer(viewer: User) -> User:
    """Main-wallet owner shown on the dashboard for the logged-in user."""
    return ledger_user_for_viewer(viewer)


def resolve_platform_payin_recipients(payer_user: Optional[User] = None) -> List[User]:
    """
    Resolution order (always a single recipient so the full fee lands on one Main wallet):
    1. ``PLATFORM_PAYIN_SETTLEMENT_USER_ID`` (pk) — primary platform recipient.
    2. First active Admin by id (case-insensitive role).
    3. First active Super Admin by id.
    4. First active superuser by id.
    5. First active Admin in the payer's upline (onboarding parent chain).
    6. Empty — amounts stay on CommissionLedger with ``user=None`` (logged).

    Multiple Admin / Super Admin logins must not evenly-split service fees; set
    ``PLATFORM_PAYIN_SETTLEMENT_USER_ID`` when the primary recipient is not the
    lowest-id Admin.
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

    admin = (
        User.objects.filter(is_active=True, role__iexact='Admin').order_by('id').first()
    )
    if admin:
        return [admin]

    super_admin = (
        User.objects.filter(is_active=True, role__iexact='Super Admin').order_by('id').first()
    )
    if super_admin:
        return [super_admin]

    superuser = User.objects.filter(is_active=True, is_superuser=True).order_by('id').first()
    if superuser:
        return [superuser]

    if payer_user:
        for parent in upline_chain(payer_user):
            if not parent.is_active:
                continue
            role = (getattr(parent, 'role', None) or '').strip().lower()
            if role in ('admin', 'super admin'):
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
            'pay_in_settlement: no recipients for platform slices (profit wallet will stay 0). '
            'txn=%s payer_id=%s gw=%s admin_total=%s — set PLATFORM_PAYIN_SETTLEMENT_USER_ID or ensure '
            'an active Admin / superuser exists.',
            transaction_id,
            payer_id,
            gateway_amount,
            admin_amount,
        )


@transaction.atomic
def sync_platform_operator_treasury() -> dict:
    """
    Merge Admin/Super Admin fee wallets + ledgers onto the treasury user so every
    operator login shows the same Main balance and commission totals.

    For each (reference_service_id, slice_key) among operators, keeps one ledger
    row on the treasury with amount = sum of the even-split parts (correct pool).
    Moves non-treasury Main balances onto the treasury with passbook reclass lines.
    """
    from apps.transactions.models import CommissionLedger, PassbookEntry
    from apps.wallets.models import Wallet

    treasury = get_platform_treasury_user()
    if not treasury:
        return {'ok': False, 'error': 'no treasury user'}

    op_ids = platform_operator_user_ids()
    other_ids = [i for i in op_ids if i != treasury.pk]
    stats = {
        'ok': True,
        'treasury_id': treasury.pk,
        'operator_ids': op_ids,
        'ledger_groups_merged': 0,
        'ledger_rows_removed': 0,
        'wallet_moved': '0.0000',
    }
    if not other_ids:
        return stats

    # --- Ledger: one row per (service_id, slice_key) on treasury ---
    op_rows = list(
        CommissionLedger.objects.filter(user_id__in=op_ids)
        .exclude(slice_key__endswith='_reversal')
        .order_by('id')
    )
    groups: dict[tuple[str, str], list] = {}
    for row in op_rows:
        key = (row.reference_service_id or '', row.slice_key or '')
        groups.setdefault(key, []).append(row)

    for (_sid, _sk), rows in groups.items():
        if len(rows) == 1 and rows[0].user_id == treasury.pk:
            continue
        total = money_q(sum((r.amount for r in rows), Decimal('0')))
        keep = next((r for r in rows if r.user_id == treasury.pk), rows[0])
        if keep.user_id != treasury.pk:
            # Avoid unique clash: clear other treasury duplicates first (none expected)
            keep.user = treasury
        keep.amount = total
        if keep.customer_charge is None or money_q(keep.customer_charge) <= 0:
            keep.customer_charge = total
        keep.save(update_fields=['user', 'amount', 'customer_charge', 'updated_at'])
        removed = 0
        for r in rows:
            if r.pk == keep.pk:
                continue
            r.delete()
            removed += 1
        if removed or len(rows) > 1 or keep.user_id == treasury.pk:
            stats['ledger_groups_merged'] += 1
            stats['ledger_rows_removed'] += removed

    # --- Main wallets: move other operator balances onto treasury ---
    moved = Decimal('0')
    for oid in other_ids:
        other = User.objects.filter(pk=oid).first()
        if not other:
            continue
        src = Wallet.objects.filter(user=other, wallet_type='main', is_archived=False).first()
        if not src:
            continue
        bal = money_q(src.balance)
        held = money_q(getattr(src, 'held_balance', 0) or 0)
        transferable = money_q(bal - held)
        if transferable <= 0:
            continue
        dest = Wallet.get_wallet(treasury, 'main')
        ob_src = money_q(src.balance)
        src.debit(
            transferable,
            reference='PLATFORM_TREASURY_SYNC',
            description='Sync operator login wallet into platform treasury',
            respect_holds=False,
        )
        src.refresh_from_db()
        PassbookEntry.objects.create(
            user=other,
            wallet_type='main',
            service='TREASURY SYNC',
            service_id='PLATFORM_TREASURY_SYNC',
            description=f'Move balance to platform treasury user {treasury.pk}',
            debit_amount=transferable,
            credit_amount=Decimal('0'),
            opening_balance=ob_src,
            closing_balance=money_q(src.balance),
            service_charge=Decimal('0'),
            principal_amount=transferable,
        )
        ob_dst = money_q(dest.balance)
        dest.credit(
            transferable,
            reference='PLATFORM_TREASURY_SYNC',
            description=f'Sync from operator login user {oid}',
        )
        dest.refresh_from_db()
        PassbookEntry.objects.create(
            user=treasury,
            wallet_type='main',
            service='TREASURY SYNC',
            service_id='PLATFORM_TREASURY_SYNC',
            description=f'Sync from operator login user {oid}',
            debit_amount=Decimal('0'),
            credit_amount=transferable,
            opening_balance=ob_dst,
            closing_balance=money_q(dest.balance),
            service_charge=Decimal('0'),
            principal_amount=transferable,
        )
        moved = money_q(moved + transferable)

    stats['wallet_moved'] = str(moved)
    logger.info('platform treasury sync complete: %s', stats)
    return stats
