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


def _amount_within_limit(amount_paise: int, min_amount: Decimal, max_amount: Decimal) -> bool:
    min_paise = int((Decimal(str(min_amount or 0)) * Decimal('100')).to_integral_value())
    max_paise = int((Decimal(str(max_amount or 0)) * Decimal('100')).to_integral_value())
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
            raise TransactionFailed(f'Amount out of allowed range for channel {channel} and biller {biller.biller_id}.')

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
            raise TransactionFailed(f'Amount out of allowed range for payment mode "{payment_mode}".')

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
    session = (
        BbpsFetchSession.objects.filter(
            user=user,
            biller_master=biller,
            is_deleted=False,
            status='FETCHED',
        )
        .order_by('-created_at')
        .first()
    )
    if not session:
        raise TransactionFailed(
            'Fetch is mandatory for this biller. Please fetch the bill before payment. '
            'If a previous payment attempt failed or was declined, fetch the bill again before retrying.'
        )
    existing_inputs = ((session.input_params or {}).get('input') or [])
    if params and existing_inputs and params != existing_inputs:
        raise TransactionFailed('Payment input parameters do not match latest fetched bill snapshot.')
    if request_id and _normalize_text(session.request_id) and request_id != session.request_id:
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
