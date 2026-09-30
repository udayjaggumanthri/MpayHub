"""
Unified revenue / commission settlement engine.

Hierarchy commission credits go through ``settle_service_charge`` onto the
beneficiary's main wallet with a matching CommissionLedger row.

Pay-in leftover and BBPS extra debit settle as ``entry_kind=commission`` onto
the platform treasury Main wallet (admin/platform profit).

Payout and bank-verification charges are **gateway costs** paid to providers —
``entry_kind=service_fee``, Service Fee Tracker only, **never** credit Admin Main.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from django.db import IntegrityError, transaction as db_transaction
from django.db.models import Q

from apps.authentication.models import User
from apps.fund_management.commission_meta import commission_ledger_create
from apps.fund_management.money_utils import money_q
from apps.fund_management.platform_settlement import resolve_platform_payin_recipients
from apps.transactions.agent_snapshot import passbook_initiator_db_fields
from apps.transactions.models import CommissionLedger, PassbookEntry
from apps.wallets.models import Wallet

logger = logging.getLogger(__name__)

# Modules whose default platform slice is admin/platform commission (credits treasury).
PLATFORM_COMMISSION_MODULES = frozenset({'payin', 'bbps', 'profit'})

# Gateway costs: ledger/tracker only — must never credit Admin / treasury Main.
GATEWAY_FEE_MODULES = frozenset({'payout', 'bank_verification'})


def _source_agent_meta(payer: Optional[User]) -> dict:
    if not payer:
        return {}
    from apps.transactions.agent_snapshot import display_name_for_user

    return {
        'source_user_id': payer.pk,
        'source_user_code': getattr(payer, 'user_id', '') or getattr(payer, 'display_code', '') or '',
        'source_role': getattr(payer, 'role', '') or '',
        'source_name': display_name_for_user(payer),
    }


def _commission_source_index_fields(src: dict) -> dict:
    return {
        'source_user_code': str(src.get('source_user_code') or '')[:30],
        'source_role': str(src.get('source_role') or '')[:50],
        'source_name_snapshot': str(src.get('source_name') or '')[:255],
    }


def resolve_platform_recipients_or_fallback(payer: Optional[User] = None) -> list[User]:
    """
    Deterministic single platform recipient. Never returns empty when any active
    Admin / superuser / Super Admin exists — prevents unattributed revenue.

    Always at most one user so the full customer charge credits one Main wallet
    (no even-split across multiple Admins).
    """
    recipients = resolve_platform_payin_recipients(payer)
    if recipients:
        return recipients[:1]

    # Broader fallback: first Super Admin, then first Admin, then first staff.
    for role in ('Super Admin', 'Admin'):
        user = User.objects.filter(is_active=True, role__iexact=role).order_by('id').first()
        if user:
            logger.warning(
                'fee_settlement: using fallback role=%s recipient=%s',
                role,
                user.pk,
            )
            return [user]

    staff = User.objects.filter(is_active=True, is_staff=True).order_by('id').first()
    if staff:
        logger.warning('fee_settlement: using fallback staff user=%s', staff.pk)
        return [staff]

    logger.error('fee_settlement: NO platform recipient available — charge will be ledger-only')
    return []


def _passbook_credit_main(
    user: User,
    *,
    service: str,
    service_id: str,
    description: str,
    amount: Decimal,
    reference: str,
    initiator: Optional[User] = None,
    service_charge: Decimal = Decimal('0'),
    principal_amount: Optional[Decimal] = None,
) -> None:
    amount = money_q(amount)
    if amount <= 0:
        return
    w = Wallet.get_wallet(user, 'main')
    ob = money_q(w.balance)
    w.credit(amount, reference=reference, description=description)
    w.refresh_from_db()
    cb = money_q(w.balance)
    init = initiator if initiator is not None else user
    PassbookEntry.objects.create(
        user=user,
        wallet_type='main',
        service=service,
        service_id=service_id,
        description=description,
        debit_amount=Decimal('0'),
        credit_amount=amount,
        opening_balance=ob,
        closing_balance=cb,
        service_charge=money_q(service_charge),
        principal_amount=money_q(principal_amount) if principal_amount is not None else amount,
        **passbook_initiator_db_fields(init),
    )


def _split_evenly(total: Decimal, n: int) -> list[Decimal]:
    if n <= 0:
        return []
    total = money_q(total)
    base = money_q(total / n)
    parts = [base] * n
    remainder = money_q(total - sum(parts))
    if remainder and parts:
        parts[0] = money_q(parts[0] + remainder)
    return parts


def _default_platform_slices(
    *,
    module: str,
    service_id: str,
    charge: Decimal,
    recipients: list[User],
) -> list[dict[str, Any]]:
    """Build default slices when caller does not pass explicit ``slices``."""
    as_commission = (
        module in PLATFORM_COMMISSION_MODULES
        and module not in GATEWAY_FEE_MODULES
    )
    if as_commission:
        slice_key = 'bbps_admin' if module == 'bbps' else 'admin_absorbed'
        entry_kind = 'commission'
        service_label = 'COMMISSION'
        description = f'{module.upper()} platform commission on {service_id}'
        source = 'payin' if module == 'payin' else module
    else:
        slice_key = 'platform_fee'
        entry_kind = 'service_fee'
        service_label = 'SERVICE FEE'
        description = f'{module.upper()} service fee on {service_id}'
        source = module if module in (
            'payin', 'profit', 'bbps', 'payout', 'bank_verification', 'aeps', 'cms'
        ) else 'profit'

    parts = _split_evenly(charge, len(recipients))
    slices: list[dict[str, Any]] = []
    for user, part in zip(recipients, parts):
        if part <= 0:
            continue
        slices.append({
            'user': user,
            'amount': part,
            'slice_key': slice_key,
            'entry_kind': entry_kind,
            'role_at_time': 'PLATFORM',
            'source': source,
            'service_label': service_label,
            'description': description,
        })
    return slices


@db_transaction.atomic
def settle_service_charge(
    *,
    payer: User,
    module: str,
    service_id: str,
    charge: Decimal,
    principal: Decimal = Decimal('0'),
    slices: Optional[list[dict[str, Any]]] = None,
    meta: Optional[dict] = None,
    credit_wallets: bool = True,
) -> list[CommissionLedger]:
    """
    Settle a customer service charge into CommissionLedger (+ wallets for commissions).

    ``slices`` is an optional explicit list of:
      { user, amount, slice_key, entry_kind, role_at_time, source, service_label, description }

    When ``slices`` is None and ``charge > 0``:
      - ``payin`` / ``bbps`` → ``entry_kind=commission`` on treasury Main (credits wallet)
      - ``payout`` and other modules → ``entry_kind=service_fee`` tracker-only

    Commission slices credit the beneficiary Main wallet when ``credit_wallets`` is True.
    """
    charge = money_q(charge or 0)
    principal = money_q(principal or 0)
    if charge <= 0 and not slices:
        return []

    src = _source_agent_meta(payer)
    src.update(meta or {})
    src_idx = _commission_source_index_fields(src)
    created: list[CommissionLedger] = []
    module_norm = (module or '').strip().lower()

    if slices is None:
        recipients = resolve_platform_recipients_or_fallback(payer)
        if not recipients:
            # Ledger-only unattributed row
            as_commission = module_norm in PLATFORM_COMMISSION_MODULES
            try:
                row = commission_ledger_create(
                    user=None,
                    role_at_time='PLATFORM',
                    amount=charge,
                    source=module_norm if module_norm != 'payin' else 'profit',
                    entry_kind='commission' if as_commission else 'service_fee',
                    module=module_norm,
                    slice_key='unattributed',
                    customer_charge=charge,
                    reference_service_id=service_id,
                    wallet_type='main',
                    meta={
                        'slice': 'unattributed',
                        'wallet_credited': False,
                        'tracker': 'commission' if as_commission else 'service_fee',
                        **src,
                    },
                    **src_idx,
                )
                created.append(row)
            except Exception:
                logger.exception('fee_settlement: failed unattributed ledger for %s', service_id)
            return created

        slices = _default_platform_slices(
            module=module_norm,
            service_id=service_id,
            charge=charge,
            recipients=recipients,
        )

    for item in slices:
        user = item.get('user')
        amount = money_q(item.get('amount') or 0)
        if amount == 0:
            continue
        slice_key = str(item.get('slice_key') or 'slice')[:64]
        entry_kind = item.get('entry_kind') or 'service_fee'
        source = item.get('source') or module_norm
        role_at_time = item.get('role_at_time') or (getattr(user, 'role', '') if user else 'PLATFORM')
        service_label = item.get('service_label') or (
            'COMMISSION' if entry_kind == 'commission' else 'SERVICE FEE'
        )
        description = item.get('description') or f'{service_label} on {service_id}'

        # Idempotency: skip if this slice already exists for this user+service.
        if user is not None and slice_key:
            exists = CommissionLedger.objects.filter(
                reference_service_id=service_id,
                user=user,
                slice_key=slice_key,
            ).exists()
            if exists:
                existing = CommissionLedger.objects.filter(
                    reference_service_id=service_id,
                    user=user,
                    slice_key=slice_key,
                ).first()
                if existing:
                    created.append(existing)
                continue

        # Commission credits Main; gateway/service fees are tracker-only.
        # Hard-block wallet credit for payout / bank_verification even if a caller
        # accidentally passes entry_kind=commission.
        module_is_gateway_fee = module_norm in GATEWAY_FEE_MODULES
        do_wallet_credit = (
            credit_wallets
            and entry_kind == 'commission'
            and not module_is_gateway_fee
            and user is not None
            and amount > 0
        )
        if module_is_gateway_fee:
            entry_kind = 'service_fee'
        if do_wallet_credit:
            _passbook_credit_main(
                user,
                service=service_label,
                service_id=service_id,
                description=description,
                amount=amount,
                reference=service_id,
                initiator=payer,
                service_charge=Decimal('0'),
                principal_amount=principal if principal else amount,
            )

        slice_meta = {
            'slice': slice_key,
            'tracker': 'service_fee' if entry_kind == 'service_fee' else 'commission',
            **src,
        }
        slice_meta.update(item.get('meta') or {})
        # Force after merge so caller meta cannot claim a wallet credit for gateway fees.
        slice_meta['wallet_credited'] = bool(do_wallet_credit)
        if module_is_gateway_fee:
            slice_meta['tracker'] = 'service_fee'
            slice_meta['wallet_credited'] = False
        try:
            row = commission_ledger_create(
                user=user,
                role_at_time=str(role_at_time)[:50],
                amount=amount,
                source=source,
                entry_kind=entry_kind,
                module=module_norm,
                slice_key=slice_key,
                customer_charge=charge if charge > 0 else money_q(item.get('customer_charge') or 0),
                reference_service_id=service_id,
                wallet_type='main',
                meta=slice_meta,
                **src_idx,
            )
            created.append(row)
        except IntegrityError:
            existing = CommissionLedger.objects.filter(
                reference_service_id=service_id,
                user=user,
                slice_key=slice_key,
            ).first()
            if existing:
                created.append(existing)
        except Exception:
            logger.exception(
                'fee_settlement: ledger create failed service_id=%s slice=%s',
                service_id,
                slice_key,
            )

    return created


@db_transaction.atomic
def clawback_settlement(
    *,
    service_id: str,
    reason: str = 'reversal',
) -> list[CommissionLedger]:
    """
    Reverse previously settled commission/fee rows for a service_id.
    Debits the beneficiary main wallet and writes compensating ledger rows.
    """
    originals = list(
        CommissionLedger.objects.filter(reference_service_id=service_id)
        .exclude(slice_key__endswith='_reversal')
        .filter(amount__gt=0)
    )
    created: list[CommissionLedger] = []
    for orig in originals:
        rev_key = f"{orig.slice_key or 'slice'}_reversal"[:64]
        if CommissionLedger.objects.filter(
            reference_service_id=service_id,
            user=orig.user,
            slice_key=rev_key,
        ).exists():
            continue
        meta_orig = dict(orig.meta or {})
        # Explicit False = tracker-only. Missing key: treat as credited (legacy).
        wallet_was_credited = meta_orig.get('wallet_credited')
        if wallet_was_credited is None:
            wallet_was_credited = True
        if orig.user_id and orig.amount > 0 and wallet_was_credited:
            w = Wallet.get_wallet(orig.user, 'main')
            try:
                ob = money_q(w.balance)
                w.debit(
                    money_q(orig.amount),
                    reference=f'{service_id}:rev',
                    description=f'Clawback {reason} for {service_id}',
                    respect_holds=False,
                )
                w.refresh_from_db()
                PassbookEntry.objects.create(
                    user=orig.user,
                    wallet_type='main',
                    service='REVENUE CLAWBACK',
                    service_id=service_id,
                    description=f'Clawback ({reason}) of {orig.slice_key} on {service_id}',
                    debit_amount=money_q(orig.amount),
                    credit_amount=Decimal('0'),
                    opening_balance=ob,
                    closing_balance=money_q(w.balance),
                    service_charge=Decimal('0'),
                    principal_amount=money_q(orig.amount),
                )
            except Exception:
                logger.exception('clawback debit failed for ledger=%s', orig.pk)

        meta = dict(orig.meta or {})
        meta['slice'] = rev_key
        meta['reversal_of'] = orig.pk
        meta['reason'] = reason
        row = commission_ledger_create(
            user=orig.user,
            role_at_time=orig.role_at_time,
            amount=money_q(orig.amount),
            source=orig.source,
            entry_kind=orig.entry_kind,
            module=orig.module or '',
            slice_key=rev_key,
            customer_charge=orig.customer_charge,
            reference_service_id=service_id,
            wallet_type='main',
            meta=meta,
            source_user_code=orig.source_user_code,
            source_role=orig.source_role,
            source_name_snapshot=orig.source_name_snapshot,
        )
        # Represent clawback as negative amount for reporting
        CommissionLedger.objects.filter(pk=row.pk).update(amount=money_q(-orig.amount))
        row.refresh_from_db()
        created.append(row)
    return created


def unattributed_revenue_queryset():
    """Admin view: ledger rows with no wallet user."""
    return CommissionLedger.objects.filter(Q(user__isnull=True) | Q(slice_key='unattributed'))
