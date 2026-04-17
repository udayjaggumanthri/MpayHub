"""
Fund management business logic services.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import transaction as db_transaction

from apps.admin_panel.models import PaymentGateway, PayoutGateway
from apps.bank_accounts.models import BankAccount
from apps.contacts.models import Contact
from apps.authentication.models import User
from apps.core.exceptions import InsufficientBalance, TransactionFailed
from apps.core.utils import decrypt_secret_payload
from apps.core.utils import generate_service_id
from apps.fund_management.models import LoadMoney, PayInPackage, Payout
from apps.fund_management.payin_hierarchy import upline_chain
from apps.fund_management.platform_settlement import (
    log_missing_platform_recipients,
    resolve_platform_payin_recipients,
)
from apps.transactions.agent_snapshot import (
    card_last4_from_payment_meta,
    passbook_initiator_db_fields,
    transaction_agent_db_fields,
)
from apps.transactions.models import CommissionLedger, PassbookEntry, Transaction
from apps.wallets.models import Wallet

logger = logging.getLogger(__name__)


def money_q(v) -> Decimal:
    """
    Quantize money to 4 dp safely (enterprise ledger / reporting).
    Accepts Decimal/float/int/str to avoid runtime errors from mixed numeric sources.
    """
    return Decimal(str(v)).quantize(Decimal('0.0001'))


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


def calculate_service_charge(amount, gateway_id=None, transaction_type='payin'):
    """
    Legacy: single percentage charge (gateway row or default).
    """
    amount = money_q(Decimal(str(amount)))
    if gateway_id:
        try:
            gateway = PaymentGateway.objects.get(id=gateway_id, status='active')
            charge_rate = Decimal(str(gateway.charge_rate)) / Decimal('100')
            charge = money_q(amount * charge_rate)
            net_amount = money_q(amount - charge)
            return {
                'charge_rate': gateway.charge_rate,
                'charge': charge,
                'net_amount': net_amount,
            }
        except PaymentGateway.DoesNotExist:
            pass

    if transaction_type == 'payin':
        charge_rate = Decimal('0.01')
    else:
        charge_rate = Decimal('0.001')

    charge = money_q(amount * charge_rate)
    net_amount = money_q(amount - charge)
    return {
        'charge_rate': float(charge_rate * 100),
        'charge': charge,
        'net_amount': net_amount,
    }


def payout_slab_charge(amount: Decimal) -> Decimal:
    amount = money_q(amount)
    low_max = getattr(settings, 'PAYOUT_SLAB_LOW_MAX', Decimal('24999'))
    low_c = getattr(settings, 'PAYOUT_CHARGE_LOW', Decimal('7'))
    high_c = getattr(settings, 'PAYOUT_CHARGE_HIGH', Decimal('15'))
    try:
        from apps.admin_panel.models import PayoutSlabConfig

        cfg = (
            PayoutSlabConfig.objects.filter(is_active=True)
            .only('low_max_amount', 'low_charge', 'high_charge')
            .order_by('-updated_at', '-id')
            .first()
        )
        if cfg:
            low_max = Decimal(str(cfg.low_max_amount))
            low_c = money_q(cfg.low_charge)
            high_c = money_q(cfg.high_charge)
    except Exception:
        # Fallback to settings constants when admin config table is unavailable.
        pass
    if amount <= low_max:
        return low_c
    return high_c


def max_payout_eligible(balance: Decimal) -> Decimal:
    balance = money_q(Decimal(str(balance)))
    if balance <= 0:
        return Decimal('0')
    low_max = getattr(settings, 'PAYOUT_SLAB_LOW_MAX', Decimal('24999'))
    low_c = getattr(settings, 'PAYOUT_CHARGE_LOW', Decimal('7'))
    high_c = getattr(settings, 'PAYOUT_CHARGE_HIGH', Decimal('15'))
    try:
        from apps.admin_panel.models import PayoutSlabConfig

        cfg = (
            PayoutSlabConfig.objects.filter(is_active=True)
            .only('low_max_amount', 'low_charge', 'high_charge')
            .order_by('-updated_at', '-id')
            .first()
        )
        if cfg:
            low_max = Decimal(str(cfg.low_max_amount))
            low_c = money_q(cfg.low_charge)
            high_c = money_q(cfg.high_charge)
    except Exception:
        pass
    cand_low = Decimal('0')
    if balance >= low_c:
        cand_low = money_q(min(low_max, balance - low_c))
        if cand_low < 0:
            cand_low = Decimal('0')
    cand_high = Decimal('0')
    threshold = low_max + Decimal('1')
    if balance >= high_c + threshold:
        ch = money_q(balance - high_c)
        if ch >= threshold:
            cand_high = ch
    return max(cand_low, cand_high)


CHAIN_COMMISSION_ROLES = ('Super Distributor', 'Master Distributor', 'Distributor')


def _chain_role_assignments(chain_parents: list) -> dict:
    """
    Map each chain role to the nearest upline user (closest to the payer first).
    chain_parents: [immediate_parent, ..., top] from upline_chain order.
    """
    out = {r: None for r in CHAIN_COMMISSION_ROLES}
    for u in chain_parents:
        role = (getattr(u, 'role', None) or '').strip()
        if role in out and out[role] is None:
            out[role] = u
    return out


def _pct_amount(gross: Decimal, pct_val) -> Decimal:
    return money_q(gross * Decimal(str(pct_val)) / Decimal('100'))


def _compute_payin_distribution(package: PayInPackage, gross: Decimal, payer_user: Optional[User] = None) -> dict:
    """
    Fee slices on gross: gateway + admin (incl. absorbed missing chain + package retailer %) + SD/MD/D payouts.

    Missing Distributor / Master / Super in the payer's upline: that slice **rolls up** to the nearest present
    upline (DT → MD → SD). Anything that cannot be placed (no SD/MD/D above the retailer) is added to the
    platform Admin share.

    The package ``retailer_commission_pct`` is merged into the platform Admin share, not the retailer's
    commission wallet.
    """
    gross = money_q(Decimal(str(gross)))
    if gross < package.min_amount or gross > package.max_amount_per_txn:
        raise ValueError(
            f'Amount must be between ₹{package.min_amount} and ₹{package.max_amount_per_txn} for this package.'
        )

    pct_base = Decimal('100')
    gw = _pct_amount(gross, package.gateway_fee_pct)
    ad_base = _pct_amount(gross, package.admin_pct)
    sd_full = _pct_amount(gross, package.super_distributor_pct)
    md_full = _pct_amount(gross, package.master_distributor_pct)
    dt_full = _pct_amount(gross, package.distributor_pct)
    retailer_absorbed = _pct_amount(gross, package.retailer_commission_pct)

    payer_role = None
    if payer_user is None:
        sd_p, md_p, dt_p = sd_full, md_full, dt_full
        absorbed_to_admin = money_q(Decimal('0'))
        ad_total = money_q(ad_base + retailer_absorbed)
        assign = {r: None for r in CHAIN_COMMISSION_ROLES}
        hierarchy_adjusted = False
    else:
        assign = _chain_role_assignments(upline_chain(payer_user))
        payer_role = (getattr(payer_user, 'role', None) or '').strip()
        # Always seed the performer's own role slice to self before roll-up logic.
        if payer_role in CHAIN_COMMISSION_ROLES:
            assign[payer_role] = payer_user
        rem = money_q(Decimal('0'))
        if assign['Distributor']:
            dt_p = dt_full
        else:
            dt_p = money_q(Decimal('0'))
            rem = money_q(rem + dt_full)
        if assign['Master Distributor']:
            md_p = money_q(md_full + rem)
            rem = money_q(Decimal('0'))
        else:
            md_p = money_q(Decimal('0'))
            rem = money_q(rem + md_full)
        if assign['Super Distributor']:
            sd_p = money_q(sd_full + rem)
            rem = money_q(Decimal('0'))
        else:
            sd_p = money_q(Decimal('0'))
            rem = money_q(rem + sd_full)
        absorbed_to_admin = money_q(rem)
        ad_total = money_q(ad_base + retailer_absorbed + absorbed_to_admin)
        hierarchy_adjusted = any(assign[r] is None for r in CHAIN_COMMISSION_ROLES) or absorbed_to_admin > 0

    total_deduction = money_q(gw + ad_total + sd_p + md_p + dt_p)
    net_credit = money_q(gross - total_deduction)

    lines = [
        {
            'key': 'gateway_fee',
            'label': 'Gateway fee',
            'pct': str(package.gateway_fee_pct),
            'amount': str(gw),
        },
    ]
    eff_admin_pct = (ad_total / gross * pct_base) if gross else Decimal('0')
    admin_line = {
        'key': 'admin',
        'label': 'Admin share',
        'pct': str(eff_admin_pct),
        'amount': str(ad_total),
    }
    admin_notes = []
    if hierarchy_adjusted and payer_user is not None:
        admin_notes.append(
            'Missing upline roles: their package % rolls up to the nearest present Super / Master / Distributor; '
            'any remainder is included in the platform Admin row.'
        )
    if retailer_absorbed > 0:
        admin_notes.append(
            'The package retailer commission percentage is included in this platform row — it is not credited '
            'to the retailer’s commission wallet.'
        )
    if hierarchy_adjusted and payer_user is not None and retailer_absorbed > 0:
        admin_line['label'] = 'Admin share (incl. absorbed upline + retailer % to platform)'
    elif hierarchy_adjusted and payer_user is not None:
        admin_line['label'] = 'Admin share (incl. absorbed upline shares)'
    elif retailer_absorbed > 0:
        admin_line['label'] = 'Admin share (incl. package retailer % to platform)'
    if admin_notes:
        admin_line['note'] = ' '.join(admin_notes)
    lines.append(admin_line)

    if payer_user is None or sd_p > 0:
        sd_line = {
            'key': 'super_distributor',
            'label': 'Super Distributor',
            'pct': str(package.super_distributor_pct),
            'amount': str(sd_p if payer_user is not None else sd_full),
        }
        if payer_user is not None and payer_role == 'Super Distributor':
            sd_line['note'] = 'Performer receives this own-role slice.'
        lines.append(sd_line)
    if payer_user is None or md_p > 0:
        md_line = {
            'key': 'master_distributor',
            'label': 'Master Distributor',
            'pct': str(package.master_distributor_pct),
            'amount': str(md_p if payer_user is not None else md_full),
        }
        if payer_user is not None and payer_role == 'Master Distributor':
            md_line['note'] = 'Performer receives this own-role slice.'
        lines.append(md_line)
    if payer_user is None or dt_p > 0:
        dt_line = {
            'key': 'distributor',
            'label': 'Distributor',
            'pct': str(package.distributor_pct),
            'amount': str(dt_p if payer_user is not None else dt_full),
        }
        if payer_user is not None and payer_role == 'Distributor':
            dt_line['note'] = 'Performer receives this own-role slice.'
        lines.append(dt_line)

    snapshot = {
        'gross': str(gross),
        'lines': lines,
        'total_deduction': str(total_deduction),
        'net_credit': str(net_credit),
        'retailer_commission': '0.00',
        'retailer_commission_pct': str(package.retailer_commission_pct),
        'retailer_share_absorbed_to_admin': str(retailer_absorbed),
        'hierarchy_adjusted': hierarchy_adjusted,
        'absorbed_to_admin_amount': str(absorbed_to_admin) if payer_user is not None else '0.00',
    }
    return {
        'snapshot': snapshot,
        'net_credit': net_credit,
        'total_deduction': total_deduction,
        'retailer_commission': money_q(Decimal('0')),
        'retailer_absorbed_to_admin': retailer_absorbed,
        'lines': lines,
        'gw': gw,
        'ad_total': ad_total,
        'ad_base': ad_base,
        'absorbed': absorbed_to_admin,
        'sd_payout': sd_p,
        'md_payout': md_p,
        'dt_payout': dt_p,
        'sd_user': assign.get('Super Distributor') if payer_user else None,
        'md_user': assign.get('Master Distributor') if payer_user else None,
        'dt_user': assign.get('Distributor') if payer_user else None,
        'assign': assign if payer_user else {r: None for r in CHAIN_COMMISSION_ROLES},
    }


def quote_payin(package: PayInPackage, gross: Decimal, payer_user: Optional[User] = None) -> dict:
    """Build line-item breakdown; net = gross - sum(deduction slices). Pass payer_user for upline-aware admin absorption."""
    dist = _compute_payin_distribution(package, gross, payer_user)
    return {
        'snapshot': dist['snapshot'],
        'net_credit': dist['net_credit'],
        'total_deduction': dist['total_deduction'],
        'retailer_commission': dist['retailer_commission'],
        'retailer_share_absorbed_to_admin': dist['retailer_absorbed_to_admin'],
        'lines': dist['lines'],
    }


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
    CommissionLedger.objects.create(
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
            CommissionLedger.objects.create(
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
                CommissionLedger.objects.create(
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
            CommissionLedger.objects.create(
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
                CommissionLedger.objects.create(
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
        'Pay-in SUCCESS: transaction_id=%s user_id=%s net_credit=%s gross=%s provider_payment_id=%s ref=%s',
        lm.transaction_id,
        lm.user_id,
        net_credit,
        lm.amount,
        provider_payment_id or '',
        ref or '',
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


def _api_master_for_payin_razorpay(package: PayInPackage):
    """
    Resolve which ApiMaster supplies Razorpay keys for this pay-in package.

    1) Payment gateway's linked API Master (payments) — preferred for multi-provider setups.
    2) Else, first payments-type row with a Razorpay-like provider_code (is_default / priority order).
       This matches ops who configure credentials only in API Master without re-linking the gateway row.
    """
    from apps.integrations.models import ApiMaster
    from apps.integrations.razorpay_orders import is_razorpay_like_provider_code

    pg = getattr(package, 'payment_gateway', None)
    if pg and getattr(pg, 'api_master_id', None):
        am = pg.api_master
        if (
            am
            and am.provider_type == 'payments'
            and is_razorpay_like_provider_code(am.provider_code)
        ):
            return am
    if str(package.provider or '') != 'razorpay':
        return None
    qs = (
        ApiMaster.objects.filter(provider_type='payments', is_deleted=False)
        .order_by('-is_default', '-priority', 'pk')
    )
    for m in qs:
        if is_razorpay_like_provider_code(m.provider_code):
            return m
    return None


def _razorpay_keypair_for_payin_package(package: PayInPackage):
    """Resolved Razorpay key_id + key_secret from API Master (live read); optional .env fallback if unset."""
    from apps.integrations.razorpay_orders import (
        extract_razorpay_key_pair_from_secrets,
        resolve_razorpay_credentials,
    )

    key_id = None
    key_secret = None
    api_master = _api_master_for_payin_razorpay(package)
    if api_master:
        secrets = decrypt_secret_payload(api_master.secrets_encrypted or '')
        key_id, key_secret = extract_razorpay_key_pair_from_secrets(secrets)
        if not (key_id and key_secret) and (api_master.secrets_encrypted or '').strip():
            logger.warning(
                'Pay-in Razorpay: API Master id=%s (%s) has encrypted secrets but key_id/key_secret '
                'pair could not be read; check key names (key_id / key_secret) or .env fallback.',
                api_master.pk,
                api_master.provider_code,
            )
    return resolve_razorpay_credentials(key_id, key_secret)


def create_payin_order(user, *, package_id: int, gross: Decimal, contact_id: int):
    """Create pending LoadMoney; call Razorpay outside DB transaction when needed."""
    package = (
        PayInPackage.objects.filter(id=package_id, is_active=True, is_deleted=False)
        .select_related('payment_gateway', 'payment_gateway__api_master')
        .first()
    )
    if not package:
        raise ValueError('Invalid or inactive package')
    if package.provider == 'payu':
        raise TransactionFailed('PayU checkout is not enabled yet. Use a mock or Razorpay package.')

    contact = Contact.objects.filter(id=contact_id, user=user).first()
    if not contact:
        raise ValueError('Contact not found')

    q = quote_payin(package, gross, user)
    tid = generate_service_id('load_money')

    with db_transaction.atomic():
        lm = LoadMoney.objects.create(
            user=user,
            package=package,
            amount=money_q(gross),
            gateway=str(package.code),
            charge=q['total_deduction'],
            net_credit=q['net_credit'],
            fee_breakdown_snapshot=q['snapshot'],
            customer_name=contact.name,
            customer_email=contact.email,
            customer_phone=contact.phone,
            status='PENDING',
            transaction_id=tid,
        )

    response = {
        'load_money_id': lm.id,
        'transaction_id': lm.transaction_id,
        'provider': package.provider,
        'amount': str(lm.amount),
        'currency': 'INR',
        'customer_name': contact.name,
        'customer_email': contact.email,
        'customer_phone': contact.phone,
        'fee_preview': q['snapshot'],
    }

    if package.provider == 'razorpay':
        from apps.integrations.razorpay_orders import create_order as rz_order

        checkout_key_id, checkout_key_secret = _razorpay_keypair_for_payin_package(package)

        order, err = rz_order(
            amount_inr=lm.amount,
            receipt=lm.transaction_id,
            notes={'txn': lm.transaction_id},
            key_id=checkout_key_id,
            key_secret=checkout_key_secret,
        )
        if err:
            LoadMoney.objects.filter(pk=lm.pk).update(
                failure_reason=str(err),
                status='FAILED',
            )
            lm.refresh_from_db()
            if str(err) == 'not_configured':
                raise TransactionFailed(
                    'Could not create payment order: Razorpay credentials are missing. '
                    'In API Master (Payments), add credentials with keys key_id and key_secret '
                    '(Key ID in the value for key_id, secret in the value for key_secret). '
                    'Link that API Master to the payment gateway if you use several providers, '
                    'or mark one Razorpay entry as default. Optional: set RAZORPAY_KEY_ID / '
                    'RAZORPAY_KEY_SECRET in the server environment.'
                )
            raise TransactionFailed(f'Could not create payment order: {err}')

        LoadMoney.objects.filter(pk=lm.pk).update(provider_order_id=order.get('id'))
        lm.refresh_from_db()
        response['razorpay'] = {
            'key_id': checkout_key_id,
            'order_id': lm.provider_order_id,
            'amount': order.get('amount'),
            'currency': order.get('currency', 'INR'),
        }
    else:
        response['mock'] = True
        response['message'] = 'Mock provider: call POST /fund-management/pay-in/complete-mock/ with transaction_id'

    return lm, response


@db_transaction.atomic
def complete_mock_payin(user, transaction_id: str):
    lm = (
        LoadMoney.objects.select_for_update()
        .filter(transaction_id=transaction_id, user=user)
        .first()
    )
    if not lm:
        raise ValueError('Load money record not found')
    if not lm.package or lm.package.provider != 'mock':
        raise ValueError('Only mock packages can be completed via this endpoint')
    if lm.status != 'PENDING':
        return lm
    fake_pay_id = f'mockpay_{lm.transaction_id}'
    return finalize_payin_success(
        lm,
        provider_payment_id=fake_pay_id,
        gateway_reference=fake_pay_id,
        payment_method='mock',
        payment_meta={'channel': 'mock'},
    )


@db_transaction.atomic
def verify_and_finalize_razorpay_payin(
    user,
    *,
    transaction_id: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
):
    """
    After Razorpay Checkout success: verify HMAC + fetch payment status, then credit wallet.
    Use this on localhost or when webhooks are delayed; production should still configure webhooks.
    """
    from apps.integrations.razorpay_orders import (
        fetch_razorpay_payment_until_captured,
        verify_razorpay_checkout_signature,
    )

    # PostgreSQL does not allow FOR UPDATE on nullable-side OUTER JOINs.
    # Keep the row lock on LoadMoney only, then lazily read related fields.
    lm = (
        LoadMoney.objects.select_for_update()
        .filter(transaction_id=transaction_id, user=user)
        .first()
    )
    if not lm:
        raise ValueError('No pay-in record found for this reference.')
    if lm.status == 'SUCCESS':
        return lm
    if lm.status != 'PENDING':
        raise ValueError('This pay-in can no longer be completed.')
    if not lm.package or lm.package.provider != 'razorpay':
        raise ValueError('This completion path is only for Razorpay pay-ins.')
    if (lm.provider_order_id or '') != str(razorpay_order_id).strip():
        raise ValueError('Razorpay order id does not match this transaction.')

    key_id, key_secret = _razorpay_keypair_for_payin_package(lm.package)
    if not key_id or not key_secret:
        raise TransactionFailed('Razorpay credentials are not configured.')

    if not verify_razorpay_checkout_signature(
        str(razorpay_order_id).strip(),
        str(razorpay_payment_id).strip(),
        str(razorpay_signature).strip(),
        key_secret=key_secret,
    ):
        logger.warning(
            'Razorpay checkout signature failed: txn=%s order=%s payment=%s',
            transaction_id,
            razorpay_order_id,
            razorpay_payment_id,
        )
        raise TransactionFailed('Payment verification failed (invalid signature).')

    pay, fetch_err = fetch_razorpay_payment_until_captured(
        str(razorpay_payment_id).strip(), key_id=key_id, key_secret=key_secret
    )
    if fetch_err or not pay:
        raise TransactionFailed(
            fetch_err
            or 'Could not confirm a captured payment with Razorpay. '
            'If payment succeeded at Razorpay, try again in a few seconds or rely on the webhook.'
        )
    pay_status = str((pay or {}).get('status') or '').lower()
    if pay_status != 'captured':
        raise TransactionFailed(
            f'Payment could not be confirmed as captured (status={pay_status}). '
            'Retry verification shortly or ensure webhooks are configured.'
        )
    linked_order = (pay or {}).get('order_id') or ''
    if linked_order and linked_order != str(razorpay_order_id).strip():
        raise TransactionFailed('Payment does not belong to this order.')

    logger.info(
        'Pay-in Razorpay checkout verify OK: txn=%s payment_id=%s user_id=%s',
        transaction_id,
        razorpay_payment_id,
        user.pk,
    )
    rz_method, rz_meta = _payment_capture_from_razorpay_payment(pay)
    return finalize_payin_success(
        lm,
        provider_payment_id=str(razorpay_payment_id).strip(),
        gateway_reference=str(razorpay_payment_id).strip(),
        payment_method=rz_method or None,
        payment_meta=rz_meta or None,
    )


@db_transaction.atomic
def process_load_money(user, amount, gateway_id):
    """Legacy synchronous path: single gateway %; immediate success (no commission split)."""
    amount = money_q(Decimal(str(amount)))
    charge_info = calculate_service_charge(amount, gateway_id, 'payin')

    load_money = LoadMoney.objects.create(
        user=user,
        amount=amount,
        gateway=str(gateway_id or 'default'),
        charge=charge_info['charge'],
        net_credit=charge_info['net_amount'],
        fee_breakdown_snapshot={
            'legacy': True,
            'gross': str(amount),
            'charge': str(charge_info['charge']),
            'net_credit': str(charge_info['net_amount']),
        },
        status='PENDING',
        transaction_id=generate_service_id('load_money'),
    )

    try:
        gateway_transaction_id = f"GTX{load_money.transaction_id}"
        load_money.gateway_transaction_id = gateway_transaction_id
        load_money.status = 'SUCCESS'
        load_money.save(update_fields=['gateway_transaction_id', 'status'])

        _passbook_credit(
            user,
            'main',
            'LOAD MONEY',
            load_money.transaction_id,
            f"LOAD MONEY (legacy), GATEWAY: {gateway_id or 'default'}, AMOUNT: {amount}, CHARGE: {charge_info['charge']}",
            charge_info['net_amount'],
            gateway_transaction_id,
            service_charge=charge_info['charge'],
            principal_amount=amount,
        )

        Transaction.objects.create(
            user=user,
            transaction_type='payin',
            amount=amount,
            charge=charge_info['charge'],
            net_amount=charge_info['net_amount'],
            status='SUCCESS',
            service_id=load_money.transaction_id,
            reference=gateway_transaction_id,
            service_family='payin',
            bank_txn_id=gateway_transaction_id[:191],
            **transaction_agent_db_fields(user),
        )

        return load_money
    except Exception as e:
        load_money.status = 'FAILED'
        load_money.failure_reason = str(e)
        load_money.save(update_fields=['status', 'failure_reason'])
        raise TransactionFailed(f'Load money failed: {str(e)}') from e


@db_transaction.atomic
def process_payout(user, bank_account_id, amount, gateway_id=None, transfer_mode: str = 'IMPS'):
    from apps.bank_accounts.models import BankAccount

    try:
        bank_account = BankAccount.objects.get(id=bank_account_id, user=user)
    except BankAccount.DoesNotExist:
        raise ValueError('Bank account not found') from None

    amount = money_q(Decimal(str(amount)))
    charge_amt = payout_slab_charge(amount)
    platform_fee = Decimal('0')
    total_deducted = money_q(amount + charge_amt)

    main_wallet = Wallet.get_wallet(user, 'main')
    if main_wallet.balance < total_deducted:
        raise InsufficientBalance(
            f'Insufficient balance. Available: ₹{main_wallet.balance}, Required: ₹{total_deducted}'
        )

    payout = Payout.objects.create(
        user=user,
        bank_account=bank_account,
        amount=amount,
        charge=charge_amt,
        platform_fee=platform_fee,
        total_deducted=total_deducted,
        transfer_mode=transfer_mode,
        status='PENDING',
        transaction_id=generate_service_id('payout'),
    )

    try:
        gateway_transaction_id = f'PTX{payout.transaction_id}'
        payout.gateway_transaction_id = gateway_transaction_id
        payout.status = 'SUCCESS'
        payout.save(update_fields=['gateway_transaction_id', 'status'])

        opening_balance = main_wallet.balance
        main_wallet.debit(total_deducted, reference=payout.transaction_id)
        closing_balance = main_wallet.balance

        Transaction.objects.create(
            user=user,
            transaction_type='payout',
            amount=amount,
            charge=charge_amt,
            platform_fee=platform_fee,
            net_amount=total_deducted,
            status='SUCCESS',
            service_id=payout.transaction_id,
            reference=gateway_transaction_id,
            service_family='payout',
            bank_txn_id=gateway_transaction_id[:191],
            **transaction_agent_db_fields(user),
        )

        PassbookEntry.objects.create(
            user=user,
            wallet_type='main',
            service='PAYOUT',
            service_id=payout.transaction_id,
            description=(
                f'PAYOUT {transfer_mode}, A/C ..{bank_account.account_number[-4:]}, IFSC {bank_account.ifsc}, '
                f'AMOUNT ₹{amount}, CHARGE ₹{charge_amt}'
            ),
            debit_amount=total_deducted,
            credit_amount=Decimal('0'),
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            service_charge=charge_amt,
            principal_amount=amount,
            **passbook_initiator_db_fields(user),
        )

        return payout
    except Exception as e:
        payout.status = 'FAILED'
        payout.failure_reason = str(e)
        payout.save(update_fields=['status', 'failure_reason'])
        raise TransactionFailed(f'Payout failed: {str(e)}') from e


def get_available_gateways(user_role=None, gateway_type='payment'):
    """
    Returns active gateways. Access is now controlled via Package Assignment system,
    not role-based visibility.
    """
    if gateway_type == 'payment':
        return PaymentGateway.objects.filter(status='active')
    return PayoutGateway.objects.filter(status='active')


def list_active_pay_in_packages():
    return PayInPackage.objects.filter(is_active=True, is_deleted=False).order_by('sort_order', 'display_name')


# ─────────────────────────────────────────────────────────────────────────────
# Package Assignment System - Access Control Functions
# ─────────────────────────────────────────────────────────────────────────────

def get_user_accessible_packages(user: User):
    """
    Returns packages the user can access for pay-in:
    1. Packages explicitly assigned to the user
    2. If no explicit assignments exist, returns default package (if any)
    
    Admin users have access to ALL active packages.
    """
    from apps.fund_management.models import UserPackageAssignment

    # Admin users can access all packages
    user_role = (getattr(user, 'role', None) or '').strip()
    if user_role == 'Admin':
        return PayInPackage.objects.filter(is_active=True, is_deleted=False).order_by('sort_order', 'display_name')

    # Check explicit assignments
    assigned_pkg_ids = UserPackageAssignment.objects.filter(
        user=user, is_deleted=False
    ).values_list('package_id', flat=True)

    if assigned_pkg_ids:
        return PayInPackage.objects.filter(
            id__in=assigned_pkg_ids,
            is_active=True,
            is_deleted=False,
        ).order_by('sort_order', 'display_name')

    # Fallback to default package
    return PayInPackage.objects.filter(
        is_default=True,
        is_active=True,
        is_deleted=False,
    ).order_by('sort_order', 'display_name')


def get_user_assigned_packages(user: User):
    """
    Returns packages explicitly assigned to a user (for admin/upline viewing).
    Does NOT include default fallback.
    """
    from apps.fund_management.models import UserPackageAssignment

    assigned_pkg_ids = UserPackageAssignment.objects.filter(
        user=user, is_deleted=False
    ).values_list('package_id', flat=True)

    return PayInPackage.objects.filter(
        id__in=assigned_pkg_ids,
        is_deleted=False,
    ).order_by('sort_order', 'display_name')


def can_user_assign_package(assigner: User, package_id: int) -> bool:
    """
    Check if assigner has access to a package and can delegate it to others.
    Admin can assign any active package.
    Non-admin can only assign packages they have been assigned.
    """
    from apps.fund_management.models import UserPackageAssignment

    assigner_role = (getattr(assigner, 'role', None) or '').strip()
    
    # Admin can assign any active package
    if assigner_role == 'Admin':
        return PayInPackage.objects.filter(
            id=package_id, is_active=True, is_deleted=False
        ).exists()

    # Non-admin must have the package assigned to them
    return UserPackageAssignment.objects.filter(
        user=assigner,
        package_id=package_id,
        is_deleted=False,
    ).exists()


def is_user_in_downline(senior: User, junior: User) -> bool:
    """
    Check if junior is in senior's direct downline hierarchy.
    Uses the parent chain to verify.
    """
    if senior.pk == junior.pk:
        return False
    
    senior_role = (getattr(senior, 'role', None) or '').strip()
    if senior_role == 'Admin':
        return True  # Admin can assign to anyone

    # Walk up the junior's parent chain
    current = junior
    visited = set()
    while current:
        if current.pk in visited:
            break
        visited.add(current.pk)
        
        parent = getattr(current, 'parent', None)
        if parent and parent.pk == senior.pk:
            return True
        current = parent
    
    return False


def assign_package_to_user(
    *,
    assigner: User,
    target_user: User,
    package_id: int,
) -> dict:
    """
    Assign a package from assigner's pool to target_user.
    
    Validation:
    - Assigner must have access to the package (or be Admin)
    - Target must be in assigner's downline (or assigner is Admin)
    - Package must be active
    
    Returns dict with 'success', 'assignment', 'message'.
    """
    from apps.fund_management.models import UserPackageAssignment

    # Validate package exists and is active
    package = PayInPackage.objects.filter(
        id=package_id, is_active=True, is_deleted=False
    ).first()
    if not package:
        return {'success': False, 'message': 'Package not found or inactive.', 'assignment': None}

    # Check assigner can assign this package
    if not can_user_assign_package(assigner, package_id):
        return {
            'success': False,
            'message': 'You do not have access to this package and cannot assign it.',
            'assignment': None,
        }

    # Check target is in assigner's downline
    assigner_role = (getattr(assigner, 'role', None) or '').strip()
    if assigner_role != 'Admin' and not is_user_in_downline(assigner, target_user):
        return {
            'success': False,
            'message': 'You can only assign packages to users in your downline.',
            'assignment': None,
        }

    # Create or update assignment
    assignment, created = UserPackageAssignment.objects.update_or_create(
        user=target_user,
        package=package,
        defaults={
            'assigned_by': assigner,
            'is_deleted': False,
        },
    )

    if created:
        logger.info(
            'Package assigned: package=%s (%s) to user=%s by assigner=%s',
            package.pk,
            package.display_name,
            target_user.user_id,
            assigner.user_id,
        )
        return {
            'success': True,
            'message': f'Package "{package.display_name}" assigned successfully.',
            'assignment': assignment,
        }
    else:
        return {
            'success': True,
            'message': f'Package "{package.display_name}" assignment updated.',
            'assignment': assignment,
        }


def remove_package_assignment(
    *,
    remover: User,
    target_user: User,
    package_id: int,
) -> dict:
    """
    Remove a package assignment from target_user.
    
    Validation:
    - Remover must be Admin or the original assigner or an upline of target
    
    Returns dict with 'success', 'message'.
    """
    from apps.fund_management.models import UserPackageAssignment

    remover_role = (getattr(remover, 'role', None) or '').strip()

    assignment = UserPackageAssignment.objects.filter(
        user=target_user,
        package_id=package_id,
        is_deleted=False,
    ).first()

    if not assignment:
        return {'success': False, 'message': 'Assignment not found.'}

    # Permission check: Admin, original assigner, or upline can remove
    can_remove = (
        remover_role == 'Admin'
        or (assignment.assigned_by and assignment.assigned_by.pk == remover.pk)
        or is_user_in_downline(remover, target_user)
    )

    if not can_remove:
        return {
            'success': False,
            'message': 'You do not have permission to remove this assignment.',
        }

    assignment.is_deleted = True
    assignment.save(update_fields=['is_deleted', 'updated_at'])

    logger.info(
        'Package assignment removed: package=%s from user=%s by remover=%s',
        package_id,
        target_user.user_id,
        remover.user_id,
    )

    return {'success': True, 'message': 'Package assignment removed.'}


def auto_assign_default_package(user: User, assigner: User = None) -> dict:
    """
    Automatically assign the default package to a new user.
    Called during user creation.
    
    Returns dict with 'success', 'assignment', 'message'.
    """
    from apps.fund_management.models import UserPackageAssignment

    default_pkg = PayInPackage.objects.filter(
        is_default=True, is_active=True, is_deleted=False
    ).first()

    if not default_pkg:
        return {
            'success': False,
            'message': 'No default package configured.',
            'assignment': None,
        }

    assignment, created = UserPackageAssignment.objects.get_or_create(
        user=user,
        package=default_pkg,
        defaults={'assigned_by': assigner},
    )

    if created:
        logger.info(
            'Default package auto-assigned: package=%s (%s) to new user=%s',
            default_pkg.pk,
            default_pkg.display_name,
            user.user_id,
        )
        return {
            'success': True,
            'message': f'Default package "{default_pkg.display_name}" assigned.',
            'assignment': assignment,
        }
    else:
        return {
            'success': True,
            'message': 'User already has the default package.',
            'assignment': assignment,
        }


def get_assignable_packages_for_user(assigner: User):
    """
    Returns packages that the assigner can assign to their downline.
    Admin: all active packages.
    Non-admin: only packages assigned to them.
    """
    assigner_role = (getattr(assigner, 'role', None) or '').strip()
    
    if assigner_role == 'Admin':
        return PayInPackage.objects.filter(
            is_active=True, is_deleted=False
        ).order_by('sort_order', 'display_name')

    return get_user_assigned_packages(assigner)
