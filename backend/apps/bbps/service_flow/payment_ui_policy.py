"""
Configurable rules for mapping MDM payment channels/modes to partner-facing pay UI.

NPCI-style rules already intersect MDM with channel-capable instruments (see ``compliance.display_payment_modes_for_channel``).
Many MDM payloads list AGT plus POS-oriented modes but omit **Cash**, even though B2B agent collection on AGT is Cash-only
and upstream rejects POS instruments with E078/E0378 until entitlements expand.

When ``BBPS_ASSISTED_CARD_PAYMENT_UI=agt_cash_when_eligible``, credit-card / loan-repayment billers with AGT in MDM
but **no** AGT-valid mode from MDM get AGT + Cash in the UI (and implicit Cash persistence / pay allowance). Switch to
``mdm_strict`` (default) to show full MDM ∩ POS instruments only.
"""

from __future__ import annotations

from django.conf import settings

from apps.bbps.service_flow.compliance import display_payment_modes_for_channel, _normalize_mode_for_compare


STRATEGY_MDM_STRICT = 'mdm_strict'
STRATEGY_AGT_CASH_WHEN_ELIGIBLE = 'agt_cash_when_eligible'


def get_assisted_card_payment_ui_strategy() -> str:
    raw = getattr(settings, 'BBPS_ASSISTED_CARD_PAYMENT_UI', STRATEGY_MDM_STRICT)
    s = str(raw or '').strip().lower().replace('-', '_')
    if s == STRATEGY_MDM_STRICT:
        return STRATEGY_MDM_STRICT
    return STRATEGY_AGT_CASH_WHEN_ELIGIBLE


def _assisted_card_like_category(raw: str) -> bool:
    s = ' '.join(str(raw or '').strip().lower().replace('_', ' ').replace('-', ' ').split())
    if 'credit' in s and 'card' in s:
        return True
    if 'loan' in s and 'repay' in s:
        return True
    return s in ('credit card', 'loan repayment')


def assisted_card_offer_agt_cash_only(
    master,
    channel_codes_upper: list[str],
    mdm_mode_labels: list[str],
) -> bool:
    """
    True when UI should restrict to AGT + Cash for assisted card billers.

    Requires non-empty MDM mode list and empty intersection for AGT (MDM omitted Cash but listed other instruments).
    """
    if get_assisted_card_payment_ui_strategy() != STRATEGY_AGT_CASH_WHEN_ELIGIBLE:
        return False
    if not _assisted_card_like_category(getattr(master, 'biller_category', '') or ''):
        return False
    ch_codes = [str(c or '').strip().upper() for c in channel_codes_upper if str(c or '').strip()]
    if 'AGT' not in ch_codes:
        return False
    labels = [str(m or '').strip() for m in (mdm_mode_labels or []) if str(m or '').strip()]
    if not labels:
        return False
    agt_modes = display_payment_modes_for_channel('AGT', labels)
    return len(agt_modes) == 0


def mdm_labels_with_implicit_cash_for_agt(mdm_mode_labels: list[str]) -> list[str]:
    """Append canonical Cash when MDM did not list an AGT-compatible instrument."""
    out = [str(x or '').strip() for x in (mdm_mode_labels or []) if str(x or '').strip()]
    if any(_normalize_mode_for_compare(x) == 'cash' for x in out):
        return out
    out.append('Cash')
    return out


def pay_allows_implicit_agt_cash(
    *,
    biller,
    payment_mode: str,
    payment_channel: str,
) -> bool:
    """Allow Cash + AGT pay when policy applies but MDM sync has not yet inserted a Cash row."""
    if _normalize_mode_for_compare(payment_mode) != 'cash':
        return False
    if str(payment_channel or '').strip().upper() != 'AGT':
        return False
    from apps.bbps.models import BbpsBillerPaymentChannelLimit, BbpsBillerPaymentModeLimit

    ch_codes = [
        str(c.payment_channel or '').strip().upper()
        for c in BbpsBillerPaymentChannelLimit.objects.filter(biller=biller, is_deleted=False, is_active=True)
        if c.payment_channel
    ]
    mode_labels = [
        str(m.payment_mode or '').strip()
        for m in BbpsBillerPaymentModeLimit.objects.filter(biller=biller, is_deleted=False, is_active=True)
        if m.payment_mode
    ]
    return assisted_card_offer_agt_cash_only(biller, ch_codes, mode_labels)


def maybe_add_implicit_cash_payment_mode(master, *, channel_codes_upper: list[str], mdm_mode_labels: list[str]) -> bool:
    """
    After MDM persist, insert a Cash mode row when policy applies so enforcement and UI stay aligned.

    Returns True when a row was created.
    """
    from apps.bbps.models import BbpsBillerPaymentModeLimit

    if not assisted_card_offer_agt_cash_only(master, channel_codes_upper, mdm_mode_labels):
        return False
    existing = BbpsBillerPaymentModeLimit.objects.filter(biller=master, is_deleted=False, is_active=True)
    if any(_normalize_mode_for_compare(m.payment_mode) == 'cash' for m in existing):
        return False
    BbpsBillerPaymentModeLimit.objects.create(
        biller=master,
        payment_mode='Cash',
        min_amount='0',
        max_amount='0',
        is_active=True,
    )
    return True
