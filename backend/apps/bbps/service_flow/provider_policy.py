from __future__ import annotations

from typing import NamedTuple

from apps.integrations.models import BillAvenueConfig, BillAvenueModeChannelPolicy


class _PolicyRowSnapshot(NamedTuple):
    payment_mode: str
    payment_channel: str
    action: str
    biller_id: str
    biller_category: str


_POLICY_ROWS_CACHE: tuple[_PolicyRowSnapshot, ...] | None = None
_POLICY_ROWS_CACHE_CONFIG_ID: int | None = None


def _norm_mode(mode: str) -> str:
    return ' '.join(str(mode or '').strip().lower().replace('_', ' ').replace('-', ' ').split())


def _norm_channel(channel: str) -> str:
    return str(channel or '').strip().upper()


def clear_provider_policy_cache() -> None:
    """Drop in-process policy row cache (e.g. after admin policy edits)."""
    global _POLICY_ROWS_CACHE, _POLICY_ROWS_CACHE_CONFIG_ID
    _POLICY_ROWS_CACHE = None
    _POLICY_ROWS_CACHE_CONFIG_ID = None


def _active_billavenue_config():
    return BillAvenueConfig.objects.filter(is_deleted=False, enabled=True, is_active=True).first()


def _get_active_policy_rows() -> tuple[_PolicyRowSnapshot, ...]:
    """Load enabled mode/channel policy rows once per worker process."""
    global _POLICY_ROWS_CACHE, _POLICY_ROWS_CACHE_CONFIG_ID
    cfg = _active_billavenue_config()
    if not cfg:
        _POLICY_ROWS_CACHE = ()
        _POLICY_ROWS_CACHE_CONFIG_ID = None
        return ()
    if _POLICY_ROWS_CACHE is not None and _POLICY_ROWS_CACHE_CONFIG_ID == cfg.pk:
        return _POLICY_ROWS_CACHE
    rows = tuple(
        _PolicyRowSnapshot(
            payment_mode=row['payment_mode'],
            payment_channel=row['payment_channel'],
            action=row['action'],
            biller_id=row['biller_id'],
            biller_category=row['biller_category'],
        )
        for row in BillAvenueModeChannelPolicy.objects.filter(
            is_deleted=False,
            enabled=True,
            config=cfg,
        ).values('payment_mode', 'payment_channel', 'action', 'biller_id', 'biller_category')
    )
    _POLICY_ROWS_CACHE = rows
    _POLICY_ROWS_CACHE_CONFIG_ID = cfg.pk
    return rows


def provider_policy_decision_for_combo(
    *,
    biller_id: str,
    biller_category: str,
    payment_mode: str,
    payment_channel: str,
) -> bool | None:
    """
    Return provider override decision for a mode/channel pair:
    - True  => explicitly allowed
    - False => explicitly denied
    - None  => no provider override
    """
    rows = _get_active_policy_rows()
    if not rows:
        return None
    mode = _norm_mode(payment_mode)
    channel = _norm_channel(payment_channel)
    bid = str(biller_id or '').strip()
    bcat = ' '.join(str(biller_category or '').strip().lower().replace('_', ' ').replace('-', ' ').split())

    scoped: list[tuple[int, str]] = []
    for r in rows:
        if _norm_mode(r.payment_mode) != mode:
            continue
        if _norm_channel(r.payment_channel) != channel:
            continue
        rid = str(r.biller_id or '').strip()
        rcat = ' '.join(str(r.biller_category or '').strip().lower().replace('_', ' ').replace('-', ' ').split())
        if rid and rid == bid:
            scoped.append((3, r.action))
        elif (not rid) and rcat and rcat == bcat:
            scoped.append((2, r.action))
        elif (not rid) and (not rcat):
            scoped.append((1, r.action))
    if not scoped:
        return None
    highest = max(x[0] for x in scoped)
    actions = [a for lvl, a in scoped if lvl == highest]
    if 'deny' in actions:
        return False
    if 'allow' in actions:
        return True
    return None


def bootstrap_default_biller_policy_if_missing(*, biller) -> int:
    """
    Seed biller-specific allow rules from current synced biller rows.

    - Creates rules only when no biller-specific policy exists (preserves admin changes).
    - Uses BBPS channel/mode validity to avoid impossible combos.
    - Returns number of rules created.
    """
    from apps.bbps.models import BbpsBillerPaymentChannelLimit, BbpsBillerPaymentModeLimit
    from apps.bbps.service_flow.compliance import bbps_channel_accepts_payment_mode

    cfg = BillAvenueConfig.objects.filter(is_deleted=False, enabled=True, is_active=True).first()
    if not cfg or not biller:
        return 0
    bid = str(getattr(biller, 'biller_id', '') or '').strip()
    if not bid:
        return 0

    has_biller_rows = BillAvenueModeChannelPolicy.objects.filter(
        is_deleted=False,
        config=cfg,
        biller_id=bid,
    ).exists()
    if has_biller_rows:
        return 0

    ch_codes = [
        _norm_channel(x.payment_channel)
        for x in BbpsBillerPaymentChannelLimit.objects.filter(is_deleted=False, is_active=True, biller=biller)
        if str(getattr(x, 'payment_channel', '') or '').strip()
    ]
    modes = [
        str(x.payment_mode or '').strip()
        for x in BbpsBillerPaymentModeLimit.objects.filter(is_deleted=False, is_active=True, biller=biller)
        if str(getattr(x, 'payment_mode', '') or '').strip()
    ]
    if not ch_codes or not modes:
        return 0

    created = 0
    seen: set[tuple[str, str]] = set()
    for ch in ch_codes:
        for mode in modes:
            key = (_norm_channel(ch), _norm_mode(mode))
            if key in seen:
                continue
            seen.add(key)
            if not bbps_channel_accepts_payment_mode(ch, mode):
                continue
            BillAvenueModeChannelPolicy.objects.create(
                config=cfg,
                payment_mode=mode,
                payment_channel=ch,
                action='allow',
                biller_id=bid,
                biller_category='',
                enabled=True,
            )
            created += 1
    if created:
        clear_provider_policy_cache()
    return created
