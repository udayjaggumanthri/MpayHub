from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_FLOOR

from django.utils import timezone

from apps.bbps.models import (
    BbpsBillerCcf1Config,
    BbpsBillerMaster,
    BbpsBillerPlanMeta,
    BbpsBillerPaymentChannelLimit,
    BbpsBillerPaymentModeLimit,
    BbpsFetchSession,
)
from apps.core.exceptions import TransactionFailed


ZERO_HOUR_COMPLAINT_CATEGORIES = {
    'fastag',
    'dth',
    'mobile prepaid',
}


def _normalize_text(value: str) -> str:
    return str(value or '').strip()


def _normalize_key(value: str) -> str:
    return _normalize_text(value).lower().replace('_', ' ').replace('-', ' ')


def _to_paise(amount) -> int:
    return int((Decimal(str(amount)) * Decimal('100')).to_integral_value())


def _mdm_limit_to_paise(limit_value) -> int:
    """
    BBPS MDM ``minAmount`` / ``maxAmount`` on payment modes & channels are in paise.
    ``0`` means unbounded. Stored as Decimal/str from raw MDM (e.g. ``100`` = ₹1).
    """
    try:
        raw = Decimal(str(limit_value if limit_value is not None else 0))
    except Exception:
        return 0
    if raw <= 0:
        return 0
    # Values are whole paise; keep integer floor for safety on odd decimals.
    return int(raw.to_integral_value(rounding=ROUND_FLOOR))


def _amount_within_limit(amount_paise: int, min_amount: Decimal, max_amount: Decimal) -> bool:
    min_paise = _mdm_limit_to_paise(min_amount)
    max_paise = _mdm_limit_to_paise(max_amount)
    if min_paise > 0 and amount_paise < min_paise:
        return False
    if max_paise > 0 and amount_paise > max_paise:
        return False
    return True


def validate_channel_device_fields(*, init_channel: str, agent_device_info: dict) -> None:
    channel = _normalize_text(init_channel).upper()
    info = agent_device_info if isinstance(agent_device_info, dict) else {}
    missing = []
    if channel in ('MOB', 'MOBB'):
        for key in ('ip', 'imei', 'os', 'app'):
            if not _normalize_text(info.get(key)):
                missing.append(key)
    elif channel in ('INT', 'INTB'):
        for key in ('ip', 'mac'):
            if not _normalize_text(info.get(key)):
                missing.append(key)
    if missing:
        raise TransactionFailed(
            f'agent_device_info missing required field(s) for channel={channel}: {", ".join(missing)}'
        )


def _normalize_mode_for_compare(mode: str) -> str:
    return _normalize_key(mode).replace('  ', ' ')


# NPCI BBPS-style: which payment *instruments* are valid per *channel* (AGT/MOB/INT/POS).
# BillAvenue guidance: AGT = B2B (agent/counter); MOB/INT = B2C (mobile app / internet) with richer
# device context. MDM lists what the biller supports; this map rejects impossible pairs (e.g. E077 UPI + AGT).
# Many B2B profiles are AGT + Cash only upstream — see biller info + institute entitlement.
_BBPS_MODE_KEY_DISPLAY_ORDER: list[tuple[str, str]] = [
    ('cash', 'Cash'),
    ('upi', 'UPI'),
    ('bharat qr', 'Bharat QR'),
    ('debit card', 'Debit Card'),
    ('credit card', 'Credit Card'),
    ('wallet', 'Wallet'),
    ('internet banking', 'Internet Banking'),
    ('prepaid card', 'Prepaid Card'),
    ('neft', 'NEFT'),
    ('imps', 'IMPS'),
]

BBPS_CHANNEL_ALLOWED_MODE_KEYS: dict[str, frozenset[str]] = {
    # Agent-assisted retail in BillAvenue BBPS typically supports cash collection only.
    # Provider rejects card/UPI style instruments on AGT for multiple billers (E077).
    'AGT': frozenset({'cash'}),
    'POS': frozenset({'cash', 'debit card', 'credit card', 'wallet', 'prepaid card', 'upi', 'bharat qr'}),
    'MOB': frozenset({'cash', 'debit card', 'credit card', 'wallet', 'prepaid card', 'upi', 'bharat qr'}),
    'MOBB': frozenset({'cash', 'debit card', 'credit card', 'wallet', 'prepaid card', 'upi', 'bharat qr'}),
    'INT': frozenset({'internet banking', 'debit card', 'credit card', 'wallet', 'prepaid card', 'upi', 'bharat qr'}),
    'INTB': frozenset({'internet banking', 'debit card', 'credit card', 'wallet', 'prepaid card', 'upi', 'bharat qr'}),
}


def bbps_channel_accepts_payment_mode(payment_channel: str, payment_mode: str) -> bool:
    ch = _normalize_text(payment_channel).upper()
    mode_key = _normalize_mode_for_compare(payment_mode)
    allowed = BBPS_CHANNEL_ALLOWED_MODE_KEYS.get(ch)
    if allowed is None:
        return True
    return mode_key in allowed


def display_payment_modes_for_channel(payment_channel: str, mdm_mode_labels: list[str] | None) -> list[str]:
    """
    Return UI labels for payment modes valid for ``payment_channel``,
    intersected with optional MDM mode names from ``billerPaymentModes``.
    """
    from apps.integrations.bbps_client import _normalize_bbps_payment_mode

    ch = _normalize_text(payment_channel).upper()
    keys_whitelist = BBPS_CHANNEL_ALLOWED_MODE_KEYS.get(ch)

    if mdm_mode_labels:
        picked: list[str] = []
        seen: set[str] = set()
        for raw in mdm_mode_labels:
            if not str(raw or '').strip():
                continue
            canon = _normalize_bbps_payment_mode(str(raw).strip())
            mk = _normalize_mode_for_compare(canon)
            if keys_whitelist is not None and mk not in keys_whitelist:
                continue
            if mk in seen:
                continue
            seen.add(mk)
            picked.append(canon)
        return picked

    if keys_whitelist is None:
        return [disp for _k, disp in _BBPS_MODE_KEY_DISPLAY_ORDER]

    ordered: list[str] = []
    for mk, disp in _BBPS_MODE_KEY_DISPLAY_ORDER:
        if mk in keys_whitelist:
            ordered.append(disp)
    return ordered


def enforce_biller_mode_channel_constraints(
    *,
    biller: BbpsBillerMaster,
    payment_mode: str,
    payment_channel: str,
    amount,
) -> None:
    from apps.bbps.service_flow.provider_policy import provider_policy_decision_for_combo

    mode = _normalize_mode_for_compare(payment_mode)
    channel = _normalize_text(payment_channel).upper()
    amount_paise = _to_paise(amount)

    allowed_channels = list(
        BbpsBillerPaymentChannelLimit.objects.filter(
            biller=biller,
            is_deleted=False,
            is_active=True,
        )
    )
    if allowed_channels:
        names = {_normalize_text(c.payment_channel).upper() for c in allowed_channels if c.payment_channel}
        if channel not in names:
            raise TransactionFailed(
                f'Payment channel {channel} not allowed for biller {biller.biller_id}. Allowed: {", ".join(sorted(names))}'
            )
        current = [c for c in allowed_channels if _normalize_text(c.payment_channel).upper() == channel]
        if current and not any(_amount_within_limit(amount_paise, c.min_amount, c.max_amount) for c in current):
            bound = current[0]
            min_rs = (Decimal(_mdm_limit_to_paise(bound.min_amount)) / Decimal('100')).quantize(Decimal('0.01'))
            max_rs_paise = _mdm_limit_to_paise(bound.max_amount)
            max_hint = (
                f', maximum Rs {(Decimal(max_rs_paise) / Decimal("100")).quantize(Decimal("0.01"))}'
                if max_rs_paise > 0
                else ''
            )
            raise TransactionFailed(
                f'Amount out of allowed range for channel {channel} and biller {biller.biller_id} '
                f'(minimum Rs {min_rs}{max_hint}).'
            )

    allowed_modes = list(
        BbpsBillerPaymentModeLimit.objects.filter(
            biller=biller,
            is_deleted=False,
            is_active=True,
        )
    )
    if allowed_modes:
        names = {_normalize_mode_for_compare(m.payment_mode) for m in allowed_modes if m.payment_mode}
        if mode not in names:
            from apps.bbps.service_flow.payment_ui_policy import pay_allows_implicit_agt_cash

            if not pay_allows_implicit_agt_cash(
                biller=biller,
                payment_mode=payment_mode,
                payment_channel=payment_channel,
            ):
                raise TransactionFailed(
                    f'Payment mode "{payment_mode}" not allowed for biller {biller.biller_id}.'
                )
            current = []
        else:
            current = [m for m in allowed_modes if _normalize_mode_for_compare(m.payment_mode) == mode]
        if current and not any(_amount_within_limit(amount_paise, m.min_amount, m.max_amount) for m in current):
            bound = current[0]
            min_rs = (Decimal(_mdm_limit_to_paise(bound.min_amount)) / Decimal('100')).quantize(Decimal('0.01'))
            max_rs_paise = _mdm_limit_to_paise(bound.max_amount)
            max_hint = (
                f', maximum Rs {(Decimal(max_rs_paise) / Decimal("100")).quantize(Decimal("0.01"))}'
                if max_rs_paise > 0
                else ''
            )
            raise TransactionFailed(
                f'Amount out of allowed range for payment mode "{payment_mode}" '
                f'(minimum Rs {min_rs}{max_hint}).'
            )

    if channel in ('INT', 'MOB', 'AGT') and mode in (
        'internet banking',
        'neft',
        'imps',
    ):
        raise TransactionFailed(f'Payment mode "{payment_mode}" is disabled for channel {channel}.')

    biller_category = _normalize_key(biller.biller_category)
    if biller_category in ('credit card', 'loan repayment') and mode in (
        'credit card',
        'wallet',
        'prepaid card',
    ):
        raise TransactionFailed(
            f'Payment mode "{payment_mode}" is disabled for category "{biller.biller_category}".'
        )

    provider_decision = provider_policy_decision_for_combo(
        biller_id=getattr(biller, 'biller_id', ''),
        biller_category=getattr(biller, 'biller_category', ''),
        payment_mode=payment_mode,
        payment_channel=channel,
    )
    if provider_decision is False:
        raise TransactionFailed(
            f'Payment mode "{payment_mode}" is disabled for biller {biller.biller_id} on channel {channel} by provider policy.'
        )

    if not bbps_channel_accepts_payment_mode(channel, payment_mode):
        hint = (
            'Agent (AGT) supports Cash at the counter; use POS/MOB/INT for cards, UPI, or Bharat QR per NPCI '
            'channel-vs-instrument rules.'
        )
        raise TransactionFailed(
            f'Payment mode "{payment_mode}" is not valid for channel {channel} for biller {biller.biller_id}. {hint}'
        )


def _input_params_signature(rows) -> tuple[tuple[str, str], ...]:
    """Order-insensitive comparison for fetch vs pay input rows (BillAvenue cares about wire order; we validate semantics)."""
    if not isinstance(rows, list):
        return ()
    norm: list[tuple[str, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        pn = str(row.get('paramName') or row.get('param_name') or '').strip()
        pv = row.get('paramValue') if 'paramValue' in row else row.get('param_value')
        norm.append((pn.lower(), pn, '' if pv is None else str(pv).strip()))
    norm.sort(key=lambda x: x[0])
    return tuple((x[1], x[2]) for x in norm)


def enforce_fetch_pay_linkage(
    *,
    user,
    biller: BbpsBillerMaster,
    input_params: list,
    request_id: str,
) -> BbpsFetchSession | None:
    requirement = _normalize_text(biller.biller_fetch_requirement).upper()
    if requirement != 'MANDATORY':
        return None
    params = input_params if isinstance(input_params, list) else []
    rid = _normalize_text(request_id)
    base_qs = BbpsFetchSession.objects.filter(
        user=user,
        biller_master=biller,
        is_deleted=False,
        status='FETCHED',
    )
    if rid:
        session = base_qs.filter(request_id=rid).order_by('-created_at').first()
        if not session:
            raise TransactionFailed(
                'No fetched bill matches this request reference. Fetch the bill again, then pay using the '
                'same request id returned from fetch (do not start a new fetch in another tab first).'
            )
    else:
        if base_qs.count() > 1:
            raise TransactionFailed(
                'More than one fetched bill is open for this biller. Pay using the request_id from the fetch you '
                'intend to settle (returned as request_id on the fetch response), or fetch again in this screen only.'
            )
        session = base_qs.order_by('-created_at').first()
    if not session:
        raise TransactionFailed(
            'Fetch is mandatory for this biller. Please fetch the bill before payment. '
            'If a previous payment attempt failed or was declined, fetch the bill again before retrying.'
        )
    existing_inputs = ((session.input_params or {}).get('input') or [])
    if _input_params_signature(params) != _input_params_signature(existing_inputs):
        raise TransactionFailed('Payment input parameters do not match latest fetched bill snapshot.')
    if rid and _normalize_text(session.request_id) and rid != session.request_id:
        raise TransactionFailed('For mandatory fetch billers, payment request_id must match fetched request_id.')
    return session


def enforce_awaited_poll_cooling(*, attempt, minimum_minutes: int = 15) -> None:
    if _normalize_text(getattr(attempt, 'status', '')).upper() != 'AWAITED':
        return
    anchor = attempt.updated_at or attempt.created_at
    if not anchor:
        return
    next_allowed = anchor + timedelta(minutes=minimum_minutes)
    now = timezone.now()
    if now < next_allowed:
        wait_seconds = int((next_allowed - now).total_seconds())
        raise TransactionFailed(
            f'Status poll cooling active for awaited transaction. Retry after {wait_seconds} seconds.'
        )


def complaint_cooling_hours_for_category(category: str) -> int:
    if _normalize_key(category) in ZERO_HOUR_COMPLAINT_CATEGORIES:
        return 0
    return 24


def enforce_complaint_cooling(*, attempt, category_hint: str = '') -> None:
    if not attempt:
        return
    category = category_hint or ''
    if not category and attempt.bill_payment:
        category = attempt.bill_payment.bill_type or ''
    hours = complaint_cooling_hours_for_category(category)
    if hours <= 0:
        return
    anchor = getattr(attempt, 'created_at', None)
    if not anchor:
        return
    now = timezone.now()
    allowed_at = anchor + timedelta(hours=hours)
    if now < allowed_at:
        remaining_hours = (allowed_at - now).total_seconds() / 3600
        raise TransactionFailed(
            f'Complaint cooling period is active for category "{category or "unknown"}". '
            f'Please wait {remaining_hours:.1f} more hour(s).'
        )


@dataclass
class Ccf1Computation:
    ccf1_paise: int
    percent_fee: Decimal
    flat_fee: Decimal


def compute_ccf1_if_required(*, biller: BbpsBillerMaster, amount_paise: int) -> Ccf1Computation | None:
    cfg = (
        BbpsBillerCcf1Config.objects.filter(biller=biller, is_deleted=False)
        .order_by('-updated_at')
        .first()
    )
    if not cfg:
        return None
    percent = Decimal(str(cfg.percent_fee or 0))
    flat = Decimal(str(cfg.flat_fee or 0))
    base = (Decimal(amount_paise) * percent / Decimal('100')) + flat
    gross = base + (base * Decimal('18') / Decimal('100'))
    floored = int(gross.quantize(Decimal('1'), rounding=ROUND_FLOOR))
    return Ccf1Computation(ccf1_paise=max(0, floored), percent_fee=percent, flat_fee=flat)


def enforce_plan_mdm_requirement(*, biller: BbpsBillerMaster, plan_id: str = '') -> None:
    requirement = _normalize_text(getattr(biller, 'plan_mdm_requirement', '')).upper()
    if requirement in ('', 'NOT_SUPPORTED'):
        return
    active_plans = BbpsBillerPlanMeta.objects.filter(
        biller=biller,
        is_deleted=False,
        status__iexact='ACTIVE',
    )
    if requirement == 'MANDATORY':
        if not _normalize_text(plan_id):
            raise TransactionFailed(
                f'Plan selection is mandatory for biller {biller.biller_id}. Pull plans and pass plan_id.'
            )
        exists = active_plans.filter(plan_id=_normalize_text(plan_id)).exists()
        if not exists:
            raise TransactionFailed(
                f'Invalid or inactive plan_id "{plan_id}" for biller {biller.biller_id}.'
            )
    if requirement == 'OPTIONAL' and _normalize_text(plan_id):
        exists = active_plans.filter(plan_id=_normalize_text(plan_id)).exists()
        if not exists:
            raise TransactionFailed(
                f'plan_id "{plan_id}" is not ACTIVE for biller {biller.biller_id}.'
            )


def enforce_cash_pan_rule(*, amount_paise: int, payment_mode: str, customer_info: dict) -> None:
    """For cash >= 50,000 INR, PAN and customer name are mandatory."""
    mode = _normalize_mode_for_compare(payment_mode)
    if mode != 'cash':
        return
    if amount_paise < 5000000:
        return
    info = customer_info if isinstance(customer_info, dict) else {}
    pan = _normalize_text(info.get('customerPan') or info.get('customer_pan'))
    name = _normalize_text(info.get('customerName') or info.get('customer_name'))
    if not pan or not name:
        raise TransactionFailed(
            'PAN and customer name are mandatory for cash transactions >= 50000.'
        )


def _rupees_from_mixed_amount(
    value,
    *,
    bill_amount_rupees: Decimal | None = None,
    role: str = 'generic',
) -> Decimal | None:
    """
    Parse already-normalized rupee fields or additionalInfo-style values.

    Prefer ``additional_info_to_rupees`` semantics so whole-rupee integers are not ÷100.
    """
    from apps.integrations.bbps_client import additional_info_to_rupees

    return additional_info_to_rupees(value, bill_amount_rupees=bill_amount_rupees, role=role)


def _info_map_from_rows(rows) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _normalize_key(str(row.get('infoName') or row.get('info_name') or ''))
        if not key:
            continue
        val = row.get('infoValue') if 'infoValue' in row else row.get('info_value')
        out[key] = '' if val is None else str(val)
    return out


def _info_alias_value(info_map: dict[str, str], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        key = _normalize_key(alias)
        if info_map.get(key):
            return info_map[key]
    return ''


def build_payment_amount_policy(
    *,
    biller: BbpsBillerMaster | None,
    bill_amount_rupees=None,
    minimum_due_rupees=None,
    maximum_payable_rupees=None,
    additional_info_rows: list | None = None,
) -> dict:
    """
    Universal payment-amount policy from MDM exactness + fetch additionalInfo bounds.

    Custom / partial amounts are allowed when the biller is adhoc or exactness is
    Exact and below / Exact and above (within bounds). Exact billers lock to bill amount.
    """
    adhoc = bool(getattr(biller, 'biller_adhoc', False)) if biller else False
    exactness_raw = _normalize_text(getattr(biller, 'biller_payment_exactness', '') if biller else '')
    exactness = _normalize_key(exactness_raw)
    info_map = _info_map_from_rows(additional_info_rows or [])

    bill = _rupees_from_mixed_amount(bill_amount_rupees, role='total')
    if bill is None:
        bill = Decimal('0')

    min_due = _rupees_from_mixed_amount(minimum_due_rupees, bill_amount_rupees=bill, role='min')
    if min_due is None:
        min_raw = _info_alias_value(
            info_map,
            (
                'minimum amount due',
                'minimum due amount',
                'min amount due',
                'minimum due',
                'min due',
            ),
        )
        min_due = (
            _rupees_from_mixed_amount(min_raw, bill_amount_rupees=bill, role='min') if min_raw else None
        )
    if min_due is None:
        min_due = Decimal('0')

    max_pay = _rupees_from_mixed_amount(maximum_payable_rupees, bill_amount_rupees=bill, role='max')
    if max_pay is None:
        max_raw = _info_alias_value(
            info_map,
            (
                'maximum permissible amount',
                'maximum permissible recharge amount',
                'maximum amount',
                'max amount',
                'maximum payable amount',
                'max permissible amount',
                'maximum recharge amount',
            ),
        )
        max_pay = (
            _rupees_from_mixed_amount(max_raw, bill_amount_rupees=bill, role='max') if max_raw else None
        )

    allow_custom = True
    mode = 'open'
    # Base floor: any positive amount. Do NOT treat credit-card "Minimum Due" as a hard
    # pay floor for adhoc/open billers — that tag is informational + UI shortcut only.
    # MDM payment-mode min (e.g. Cash 100 paise) is enforced separately in mode/channel checks.
    floor = Decimal('0.01')
    ceiling: Decimal | None = max_pay

    if exactness == 'exact' and not adhoc:
        mode = 'exact'
        allow_custom = False
        floor = bill if bill > 0 else floor
        ceiling = bill if bill > 0 else ceiling
    elif exactness == 'exact and below':
        mode = 'exact_and_below'
        allow_custom = True
        if bill > 0:
            ceiling = bill if ceiling is None else min(ceiling, bill)
        if min_due > 0:
            floor = min_due
    elif exactness == 'exact and above':
        mode = 'exact_and_above'
        allow_custom = True
        floor = bill if bill > 0 else floor
        if min_due > 0:
            floor = max(floor, min_due)
    elif adhoc:
        mode = 'adhoc'
        allow_custom = True
        # ceiling from Maximum Permissible Amount when provider sends it
    else:
        mode = 'open'
        allow_custom = True
        # Ceiling only from provider max (additionalInfo); do not invent Exact-and-below.

    return {
        'mode': mode,
        'exactness': exactness_raw,
        'biller_adhoc': adhoc,
        'allow_custom': allow_custom,
        'bill_amount': str(bill),
        'min_amount': str(floor),
        'max_amount': str(ceiling) if ceiling is not None else '',
        'minimum_due': str(min_due),
        'maximum_payable': str(max_pay) if max_pay is not None else '',
    }


def enforce_payment_amount_policy(
    *,
    biller: BbpsBillerMaster,
    amount,
    fetch_session: BbpsFetchSession | None = None,
    additional_info_rows: list | None = None,
) -> dict:
    """
    Reject amounts that violate MDM exactness / provider min-max before calling BillAvenue.
    Custom amounts remain allowed for adhoc and Exact-and-below/above billers within bounds.
    """
    pay_amt = Decimal(str(amount))
    if pay_amt <= 0:
        raise TransactionFailed('Payment amount must be greater than zero.')

    bill_rupees = None
    min_due = None
    max_pay = None
    rows = additional_info_rows
    if fetch_session is not None:
        if rows is None:
            stored = getattr(fetch_session, 'additional_info', None)
            if isinstance(stored, list):
                rows = stored
            elif isinstance(stored, dict):
                rows = stored.get('info')
        if getattr(fetch_session, 'amount_paise', None) not in (None, ''):
            try:
                bill_rupees = Decimal(str(fetch_session.amount_paise)) / Decimal('100')
            except Exception:
                bill_rupees = None

    policy = build_payment_amount_policy(
        biller=biller,
        bill_amount_rupees=bill_rupees,
        minimum_due_rupees=min_due,
        maximum_payable_rupees=max_pay,
        additional_info_rows=rows,
    )
    floor = Decimal(str(policy['min_amount'] or '0'))
    ceiling_raw = str(policy.get('max_amount') or '').strip()
    ceiling = Decimal(ceiling_raw) if ceiling_raw else None

    if policy['mode'] == 'exact' and bill_rupees is not None and bill_rupees > 0:
        if pay_amt != bill_rupees.quantize(Decimal('0.01')) and abs(pay_amt - bill_rupees) > Decimal('0.009'):
            raise TransactionFailed(
                f'This biller requires the exact bill amount of Rs {bill_rupees}. '
                f'Custom / partial amounts are not allowed.'
            )
        return policy

    if floor > 0 and pay_amt < floor:
        raise TransactionFailed(
            f'Payment amount must be at least Rs {floor} for this biller.'
        )
    if ceiling is not None and ceiling > 0 and pay_amt > ceiling:
        raise TransactionFailed(
            f'Payment amount cannot exceed Rs {ceiling} for this biller.'
        )
    return policy
