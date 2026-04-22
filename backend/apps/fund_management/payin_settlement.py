"""
Pay-in settlement after gateway confirmation: wallet credits, Transaction row, commission distribution.

Kept separate from ``services`` to shrink the main service module and avoid circular imports.
Razorpay / PayU (when enabled) should call ``finalize_payin_success`` with a ``LoadMoney`` row locked upstream.

Future PayU webhook: match PayU merchant txn / PayU ID fields to ``LoadMoney.provider_order_id`` or
``LoadMoney.transaction_id`` per PayU response documentation before calling ``finalize_payin_success``.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction as db_transaction

from apps.authentication.models import User
from apps.core.exceptions import TransactionFailed
from apps.fund_management.commission_meta import commission_ledger_create
from apps.fund_management.models import LoadMoney, PayInPackage
from apps.fund_management.money_utils import money_q
from apps.fund_management.payin_distribution import _compute_payin_distribution
from apps.fund_management.platform_settlement import (
    log_missing_platform_recipients,
    resolve_platform_payin_recipients,
)
from apps.transactions.agent_snapshot import (
    card_last4_from_payment_meta,
    passbook_initiator_db_fields,
    transaction_agent_db_fields,
)
from apps.transactions.models import PassbookEntry, Transaction
from apps.wallets.models import Wallet

logger = logging.getLogger(__name__)


def _payin_source_agent_meta(payer: Optional[User]) -> dict:
    """Identifies the retailer (or loading user) that generated a pay-in commission."""
    if not payer:
        return {}
    name = ''
    try:
        prof = getattr(payer, 'profile', None)
        if prof is not None:
            name = (getattr(prof, 'full_name', None) or '').strip()
    except Exception:
        name = ''
    if not name:
        name = (getattr(payer, 'email', None) or '') or ''
    code = getattr(payer, 'user_id', None) or ''
    return {
        'source_user_id': payer.pk,
        'source_user_code': str(code),
        'source_role': getattr(payer, 'role', None) or '',
        'source_name': (name.strip() or str(code) or str(payer.pk)),
    }


def _commission_source_index_fields(meta: dict) -> dict:
    """Denormalized columns on CommissionLedger (fast reporting)."""
    return {
        'source_user_code': str(meta.get('source_user_code') or ''),
        'source_role': str(meta.get('source_role') or ''),
        'source_name_snapshot': str(meta.get('source_name') or meta.get('source_user_code') or ''),
    }


def _split_total_evenly(total: Decimal, parts: int) -> list[Decimal]:
    """
    Split ``total`` (money_q precision) into ``parts`` amounts that sum exactly to ``money_q(total)``.
    Remainder micro-units go to the first recipients so totals stay balanced.
    """
    total = money_q(total)
    if parts <= 0:
        return []
    if parts == 1:
        return [total]
    if total <= 0:
        return [money_q(Decimal('0'))] * parts
    micro = int((total * Decimal('10000')).to_integral_value())
    base = micro // parts
    rem = micro % parts
    out: list[Decimal] = []
    for i in range(parts):
        c = base + (1 if i < rem else 0)
        out.append(money_q(Decimal(c) / Decimal('10000')))
    return out


def _passbook_credit(
    user,
    wallet_type: str,
    service: str,
    service_id: str,
    description: str,
    amount: Decimal,
    reference: str,
    *,
    service_charge: Optional[Decimal] = None,
    principal_amount: Optional[Decimal] = None,
    initiator_user: Optional[User] = None,
):
    amount = money_q(amount)
    sc = money_q(service_charge) if service_charge is not None else Decimal('0')
    pa = money_q(principal_amount) if principal_amount is not None else amount
    w = Wallet.get_wallet(user, wallet_type)
    ob = money_q(w.balance)
    w.credit(amount, reference=reference, description=description)
    w.refresh_from_db()
    cb = money_q(w.balance)
    init = initiator_user if initiator_user is not None else user
    PassbookEntry.objects.create(
        user=user,
        wallet_type=wallet_type,
        service=service,
        service_id=service_id,
        description=description,
        debit_amount=Decimal('0'),
        credit_amount=amount,
        opening_balance=ob,
        closing_balance=cb,
        service_charge=sc,
        principal_amount=pa,
        **passbook_initiator_db_fields(init),
    )


def _passbook_debit(
    user,
    wallet_type: str,
    service: str,
    service_id: str,
    description: str,
    amount: Decimal,
    reference: str,
    *,
    service_charge: Optional[Decimal] = None,
    principal_amount: Optional[Decimal] = None,
    initiator_user: Optional[User] = None,
):
    amount = money_q(amount)
    sc = money_q(service_charge) if service_charge is not None else Decimal('0')
    pa = money_q(principal_amount) if principal_amount is not None else amount
    w = Wallet.get_wallet(user, wallet_type)
    ob = money_q(w.balance)
    w.debit(amount, reference=reference, description=description)
    w.refresh_from_db()
    cb = money_q(w.balance)
    init = initiator_user if initiator_user is not None else user
    PassbookEntry.objects.create(
        user=user,
        wallet_type=wallet_type,
        service=service,
        service_id=service_id,
        description=description,
        debit_amount=amount,
        credit_amount=Decimal('0'),
        opening_balance=ob,
        closing_balance=cb,
        service_charge=sc,
        principal_amount=pa,
        **passbook_initiator_db_fields(init),
    )


def _pay_chain_commission_slice(
    load_money: LoadMoney,
    tx_ref: str,
    *,
    user_obj: Optional[User],
    amount: Decimal,
    role_label: str,
    slice_key: str,
):
    if not user_obj or amount <= 0:
        return
    amt = money_q(amount)
    payer = load_money.user
    src = _payin_source_agent_meta(payer)
    suffix = (
        f" (from {src.get('source_user_code', '')}, {src.get('source_role', '')})"
        if src.get('source_user_code')
        else ''
    )
    _passbook_credit(
        user_obj,
        'commission',
        'COMMISSION',
        load_money.transaction_id,
        f'Pay-in commission ({role_label}) on {load_money.transaction_id}{suffix}',
        amt,
        tx_ref,
        initiator_user=payer,
    )
    commission_ledger_create(
        user=user_obj,
        role_at_time=user_obj.role,
        amount=amt,
        source='payin',
        reference_service_id=load_money.transaction_id,
        wallet_type='commission',
        meta={'slice': slice_key, **src},
        **_commission_source_index_fields(src),
    )


def _credit_platform_payin_slices(
    load_money: LoadMoney,
    *,
    gw: Decimal,
    ad_total: Decimal,
    dist: dict,
    tx_ref: str,
) -> None:
    """Credit gateway + admin platform shares into Admin profit wallet(s)."""
    recipients = resolve_platform_payin_recipients(load_money.user)
    src_meta = _payin_source_agent_meta(load_money.user)
    suffix = (
        f" (from {src_meta.get('source_user_code', '')}, {src_meta.get('source_role', '')})"
        if src_meta.get('source_user_code')
        else ''
    )
    n = len(recipients)
    if n == 0 and (gw > 0 or ad_total > 0):
        log_missing_platform_recipients(
            transaction_id=load_money.transaction_id,
            payer_id=load_money.user_id,
            gateway_amount=gw,
            admin_amount=ad_total,
        )

    src_idx = _commission_source_index_fields(src_meta)

    if gw > 0:
        if n == 0:
            commission_ledger_create(
                user=None,
                role_at_time='PLATFORM_GATEWAY',
                amount=gw,
                source='profit',
                reference_service_id=load_money.transaction_id,
                wallet_type='profit',
                meta={'slice': 'gateway_absorbed', **src_meta},
                **src_idx,
            )
        else:
            parts = _split_total_evenly(gw, n)
            for user, part in zip(recipients, parts):
                if part <= 0:
                    continue
                _passbook_credit(
                    user,
                    'profit',
                    'PROFIT',
                    load_money.transaction_id,
                    f'Pay-in platform (gateway share) on {load_money.transaction_id}{suffix}',
                    part,
                    tx_ref,
                    initiator_user=load_money.user,
                )
                commission_ledger_create(
                    user=user,
                    role_at_time='PLATFORM_GATEWAY',
                    amount=part,
                    source='profit',
                    reference_service_id=load_money.transaction_id,
                    wallet_type='profit',
                    meta={'slice': 'gateway_absorbed', 'split_recipients': n, **src_meta},
                    **src_idx,
                )

    if ad_total > 0:
        if n == 0:
            commission_ledger_create(
                user=None,
                role_at_time='PLATFORM_ADMIN',
                amount=ad_total,
                source='profit',
                reference_service_id=load_money.transaction_id,
                wallet_type='profit',
                meta={
                    'slice': 'admin_absorbed',
                    'admin_base_amount': str(dist['ad_base']),
                    'absorbed_chain_amount': str(dist['absorbed']),
                    'retailer_absorbed_to_admin': str(dist.get('retailer_absorbed_to_admin', '0')),
                    **src_meta,
                },
                **src_idx,
            )
        else:
            parts = _split_total_evenly(ad_total, n)
            for user, part in zip(recipients, parts):
                if part <= 0:
                    continue
                _passbook_credit(
                    user,
                    'profit',
                    'PROFIT',
                    load_money.transaction_id,
                    f'Pay-in platform (admin share) on {load_money.transaction_id}{suffix}',
                    part,
                    tx_ref,
                    initiator_user=load_money.user,
                )
                commission_ledger_create(
                    user=user,
                    role_at_time='PLATFORM_ADMIN',
                    amount=part,
                    source='profit',
                    reference_service_id=load_money.transaction_id,
                    wallet_type='profit',
                    meta={
                        'slice': 'admin_absorbed',
                        'admin_base_amount': str(dist['ad_base']),
                        'absorbed_chain_amount': str(dist['absorbed']),
                        'retailer_absorbed_to_admin': str(dist.get('retailer_absorbed_to_admin', '0')),
                        'split_recipients': n,
                        **src_meta,
                    },
                    **src_idx,
                )

    if gw > 0 or ad_total > 0:
        logger.info(
            'Pay-in platform commission: txn=%s recipients=%s gw=%s ad_total=%s',
            load_money.transaction_id,
            [u.pk for u in recipients] if recipients else [],
            gw,
            ad_total,
        )


@db_transaction.atomic
def _distribute_payin_commissions(load_money: LoadMoney, package: PayInPackage, gross: Decimal, tx_ref: str):
    """
    Credit commission wallets using the same upline-aware split as quote/create-order.
    Missing chain roles roll up to the nearest present upline; remainder goes to platform (Admin) settlement.
    """
    gross = money_q(gross)
    dist = _compute_payin_distribution(package, gross, load_money.user)

    _pay_chain_commission_slice(
        load_money,
        tx_ref,
        user_obj=dist['sd_user'],
        amount=dist['sd_payout'],
        role_label='Super Distributor',
        slice_key='Super Distributor',
    )
    _pay_chain_commission_slice(
        load_money,
        tx_ref,
        user_obj=dist['md_user'],
        amount=dist['md_payout'],
        role_label='Master Distributor',
        slice_key='Master Distributor',
    )
    _pay_chain_commission_slice(
        load_money,
        tx_ref,
        user_obj=dist['dt_user'],
        amount=dist['dt_payout'],
        role_label='Distributor',
        slice_key='Distributor',
    )

    gw = dist['gw']
    ad_total = dist['ad_total']
    _credit_platform_payin_slices(load_money, gw=gw, ad_total=ad_total, dist=dist, tx_ref=tx_ref)


def _payment_capture_from_razorpay_payment(pay: Optional[dict]) -> tuple[str, dict]:
    """Normalize Razorpay GET payment / webhook entity into (method, meta) for LoadMoney."""
    from apps.integrations.razorpay_orders import meta_from_razorpay_payment_entity

    if not pay or not isinstance(pay, dict):
        return '', {}
    method = str(pay.get('method') or '').strip().lower()[:32]
    meta = meta_from_razorpay_payment_entity(pay)
    return method, meta


@db_transaction.atomic
def finalize_payin_success(
    load_money: LoadMoney,
    *,
    provider_payment_id: Optional[str] = None,
    gateway_reference: Optional[str] = None,
    payment_method: Optional[str] = None,
    payment_meta: Optional[dict] = None,
):
    """
    Idempotent: credit main + commissions after payment confirmed (webhook or mock).
    """
    lm = LoadMoney.objects.select_for_update().get(pk=load_money.pk)
    if lm.status == 'SUCCESS':
        logger.info(
            'payin finalize duplicate skip (already SUCCESS)',
            extra={
                'event': 'payin_finalize_duplicate',
                'user_id': lm.user_id,
                'transaction_id': lm.transaction_id,
                'service_id': lm.transaction_id,
                'amount': str(lm.amount),
                'status': lm.status,
            },
        )
        return lm

    if provider_payment_id:
        if LoadMoney.objects.filter(provider_payment_id=provider_payment_id).exclude(pk=lm.pk).exists():
            raise TransactionFailed('Duplicate provider payment id')
        lm.provider_payment_id = provider_payment_id

    ref = gateway_reference or lm.provider_order_id or lm.transaction_id
    lm.gateway_transaction_id = ref or lm.gateway_transaction_id
    lm.status = 'SUCCESS'
    if payment_method is not None and str(payment_method).strip():
        lm.payment_method = str(payment_method).strip().lower()[:32]
    if payment_meta:
        base = dict(lm.payment_meta) if isinstance(lm.payment_meta, dict) else {}
        for k, v in payment_meta.items():
            if v is not None and v != '':
                base[str(k)[:40]] = v
        lm.payment_meta = base
    lm.save(
        update_fields=[
            'provider_payment_id',
            'gateway_transaction_id',
            'status',
            'payment_method',
            'payment_meta',
            'updated_at',
        ]
    )

    package = lm.package
    gross = money_q(lm.amount)
    if package:
        dist_settle = _compute_payin_distribution(package, gross, lm.user)
        net_credit = dist_settle['net_credit']
        total_charge = dist_settle['total_deduction']
        lm.net_credit = net_credit
        lm.charge = total_charge
        lm.fee_breakdown_snapshot = dist_settle['snapshot']
        lm.save(update_fields=['net_credit', 'charge', 'fee_breakdown_snapshot', 'updated_at'])
    else:
        net_credit = money_q(lm.net_credit)
        total_charge = money_q(lm.charge)

    logger.info(
        'payin finalize success',
        extra={
            'event': 'payin_finalize_success',
            'user_id': lm.user_id,
            'transaction_id': lm.transaction_id,
            'service_id': lm.transaction_id,
            'amount': str(lm.amount),
            'net_credit': str(net_credit),
            'status': lm.status,
            'provider_payment_id': provider_payment_id or '',
            'gateway_reference': ref or '',
        },
    )

    _passbook_credit(
        lm.user,
        'main',
        'LOAD MONEY',
        lm.transaction_id,
        f"LOAD MONEY net credit, gross ₹{gross}, ref {ref}",
        net_credit,
        ref,
        service_charge=total_charge,
        principal_amount=gross,
    )

    meta_for_card = lm.payment_meta if isinstance(lm.payment_meta, dict) else {}
    Transaction.objects.create(
        user=lm.user,
        transaction_type='payin',
        amount=gross,
        charge=total_charge,
        net_amount=net_credit,
        status='SUCCESS',
        service_id=lm.transaction_id,
        reference=ref,
        service_family='payin',
        bank_txn_id=(ref or '')[:191] or None,
        card_last4=card_last4_from_payment_meta(meta_for_card) or None,
        **transaction_agent_db_fields(lm.user),
    )

    if package:
        _distribute_payin_commissions(lm, package, gross, ref)
    return lm
