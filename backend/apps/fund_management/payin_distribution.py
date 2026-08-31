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


def _compute_payin_distribution(
    package: PayInPackage,
    gross: Decimal,
    payer_user: Optional[User] = None,
    *,
    gateway_fee_pct: Optional[Decimal] = None,
) -> dict:
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
    gw_pct = Decimal(str(gateway_fee_pct)) if gateway_fee_pct is not None else Decimal(str(package.gateway_fee_pct))
    gw = _pct_amount(gross, gw_pct)
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
            'pct': str(gw_pct),
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


def compute_payin_for_chain_presence(
    package: PayInPackage,
    gross: Decimal,
    *,
    gateway_fee_pct: Optional[Decimal] = None,
    has_super_distributor: bool = False,
    has_master_distributor: bool = False,
    has_distributor: bool = False,
) -> dict:
    """
    Admin preview helper: simulate hierarchy roll-up without real User rows.
    Roll-up order: D → MD → SD → Admin.
    """
    gross = money_q(Decimal(str(gross)))
    gw_pct = Decimal(str(gateway_fee_pct)) if gateway_fee_pct is not None else Decimal(str(package.gateway_fee_pct))
    gw = _pct_amount(gross, gw_pct)
    ad_base = _pct_amount(gross, package.admin_pct)
    sd_full = _pct_amount(gross, package.super_distributor_pct)
    md_full = _pct_amount(gross, package.master_distributor_pct)
    dt_full = _pct_amount(gross, package.distributor_pct)
    retailer_absorbed = _pct_amount(gross, package.retailer_commission_pct)

    rollup_steps: list[str] = []
    rem = money_q(Decimal('0'))

    if has_distributor:
        dt_p = dt_full
    else:
        dt_p = money_q(Decimal('0'))
        rem = money_q(rem + dt_full)
        if dt_full > 0:
            rollup_steps.append(
                f'Distributor slice ({package.distributor_pct}%) rolls up to Master Distributor'
            )

    if has_master_distributor:
        md_p = money_q(md_full + rem)
        if rem > 0 and md_full > 0:
            rollup_steps.append('Rolled-up Distributor amount merged into Master Distributor payout')
        elif rem > 0:
            rollup_steps.append('Distributor slice absorbed by Master Distributor (MD present)')
        rem = money_q(Decimal('0'))
    else:
        md_p = money_q(Decimal('0'))
        rem = money_q(rem + md_full)
        if md_full > 0 or (not has_distributor and dt_full > 0):
            rollup_steps.append(
                f'Master Distributor slice ({package.master_distributor_pct}%) rolls up to Super Distributor'
            )

    if has_super_distributor:
        sd_p = money_q(sd_full + rem)
        if rem > 0 and sd_full > 0:
            rollup_steps.append('Rolled-up MD/D amounts merged into Super Distributor payout')
        elif rem > 0:
            rollup_steps.append('Missing upline slices absorbed by Super Distributor (SD present)')
        rem = money_q(Decimal('0'))
    else:
        sd_p = money_q(Decimal('0'))
        rem = money_q(rem + sd_full)
        if sd_full > 0 or rem > sd_full:
            rollup_steps.append(
                f'Super Distributor slice ({package.super_distributor_pct}%) rolls up to Admin'
            )

    absorbed_to_admin = money_q(rem)
    if absorbed_to_admin > 0:
        rollup_steps.append(
            f'₹{absorbed_to_admin} of missing upline commission absorbed into Admin share'
        )

    ad_total = money_q(ad_base + retailer_absorbed + absorbed_to_admin)
    hierarchy_adjusted = not (has_super_distributor and has_master_distributor and has_distributor) or absorbed_to_admin > 0

    total_deduction = money_q(gw + ad_total + sd_p + md_p + dt_p)
    net_credit = money_q(gross - total_deduction)

    lines = [
        {'key': 'gateway_fee', 'label': 'Gateway fee', 'pct': str(gw_pct), 'amount': str(gw)},
    ]
    eff_admin_pct = (ad_total / gross * Decimal('100')) if gross else Decimal('0')
    admin_line = {
        'key': 'admin',
        'label': 'Admin share',
        'pct': str(eff_admin_pct),
        'amount': str(ad_total),
    }
    if hierarchy_adjusted:
        admin_line['label'] = 'Admin share (incl. absorbed upline shares)'
        admin_line['note'] = (
            'Missing upline roles: their package % rolls up to the nearest present role; '
            'remainder is included in Admin.'
        )
    lines.append(admin_line)

    role_payouts = [
        ('Super Distributor', sd_p, package.super_distributor_pct, has_super_distributor),
        ('Master Distributor', md_p, package.master_distributor_pct, has_master_distributor),
        ('Distributor', dt_p, package.distributor_pct, has_distributor),
    ]
    assignments = {}
    for role, amount, pct_val, present in role_payouts:
        if present and amount > 0:
            assignments[role] = {'name': role, 'amount': str(amount), 'status': 'paid'}
            lines.append({
                'key': role.lower().replace(' ', '_'),
                'label': role,
                'pct': str(pct_val),
                'amount': str(amount),
            })
        elif amount > 0:
            assignments[role] = {'name': None, 'amount': str(amount), 'status': 'rolls_up'}
        else:
            assignments[role] = {'name': None, 'amount': '0.00', 'status': 'rolls_up'}

    return {
        'lines': lines,
        'total_deduction': str(total_deduction),
        'net_credit': str(net_credit),
        'hierarchy': {
            'assignments': assignments,
            'absorbed_to_admin': str(absorbed_to_admin),
            'hierarchy_adjusted': hierarchy_adjusted,
            'rollup_steps': rollup_steps,
        },
    }


PREVIEW_HIERARCHY_SCENARIOS = (
    {
        'id': 'generic',
        'title': 'No payer (theoretical)',
        'description': (
            'No retailer selected. Shows full SD, MD, and D slices at package % — '
            'useful as a baseline before hierarchy roll-up.'
        ),
        'mode': 'no_payer',
    },
    {
        'id': 'admin_direct_retailer',
        'title': 'Admin → Retailer direct',
        'description': (
            'Retailer onboarded directly under Admin with no Super Distributor, Master Distributor, '
            'or Distributor in upline. All chain slices roll up to Admin.'
        ),
        'mode': 'chain',
        'has_super_distributor': False,
        'has_master_distributor': False,
        'has_distributor': False,
    },
    {
        'id': 'full_chain',
        'title': 'Full chain (SD + MD + D)',
        'description': 'Retailer has Super Distributor, Master Distributor, and Distributor in upline. Each role receives its slice.',
        'mode': 'chain',
        'has_super_distributor': True,
        'has_master_distributor': True,
        'has_distributor': True,
    },
    {
        'id': 'missing_distributor',
        'title': 'Missing Distributor',
        'description': 'SD and MD exist but no Distributor. D slice rolls to MD.',
        'mode': 'chain',
        'has_super_distributor': True,
        'has_master_distributor': True,
        'has_distributor': False,
    },
    {
        'id': 'missing_md_and_d',
        'title': 'Only Super Distributor',
        'description': 'Only SD in upline. MD and D slices roll up to SD, then remainder to Admin if needed.',
        'mode': 'chain',
        'has_super_distributor': True,
        'has_master_distributor': False,
        'has_distributor': False,
    },
)


def build_preview_hierarchy_scenarios(
    package: PayInPackage,
    gross: Decimal,
    *,
    gateway_fee_pct: Optional[Decimal] = None,
) -> list[dict]:
    """Return admin education scenarios for calculation preview."""
    out = []
    for spec in PREVIEW_HIERARCHY_SCENARIOS:
        if spec['mode'] == 'no_payer':
            dist = _compute_payin_distribution(package, gross, None, gateway_fee_pct=gateway_fee_pct)
            out.append({
                'id': spec['id'],
                'title': spec['title'],
                'description': spec['description'],
                'lines': dist['lines'],
                'total_deduction': str(dist['total_deduction']),
                'net_credit': str(dist['net_credit']),
                'hierarchy': {
                    'assignments': {
                        'Super Distributor': {
                            'name': 'Theoretical SD',
                            'amount': str(dist['sd_payout']),
                            'status': 'theoretical',
                        },
                        'Master Distributor': {
                            'name': 'Theoretical MD',
                            'amount': str(dist['md_payout']),
                            'status': 'theoretical',
                        },
                        'Distributor': {
                            'name': 'Theoretical D',
                            'amount': str(dist['dt_payout']),
                            'status': 'theoretical',
                        },
                    },
                    'absorbed_to_admin': '0.00',
                    'hierarchy_adjusted': False,
                    'rollup_steps': ['No payer — each role shown at full package %.'],
                },
            })
            continue

        result = compute_payin_for_chain_presence(
            package,
            gross,
            gateway_fee_pct=gateway_fee_pct,
            has_super_distributor=spec['has_super_distributor'],
            has_master_distributor=spec['has_master_distributor'],
            has_distributor=spec['has_distributor'],
        )
        out.append({
            'id': spec['id'],
            'title': spec['title'],
            'description': spec['description'],
            'lines': result['lines'],
            'total_deduction': result['total_deduction'],
            'net_credit': result['net_credit'],
            'hierarchy': result['hierarchy'],
        })
    return out
