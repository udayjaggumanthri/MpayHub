"""
Pay-in fee distribution (gross → gateway, admin, chain slices).
Separated from settlement so quote APIs and settlement share one implementation.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from apps.authentication.models import User
from apps.fund_management.models import PayInPackage
from apps.fund_management.money_utils import money_q
from apps.fund_management.payin_hierarchy import upline_chain

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

    Platform Admin share (``ad_total``) is later settled to Admin profit wallets via
    ``resolve_platform_payin_recipients`` in ``platform_settlement`` together with gateway fee routing.
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
