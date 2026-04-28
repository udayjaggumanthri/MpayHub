from __future__ import annotations

from typing import Iterable

from django.db import transaction
from django.utils import timezone

from apps.bbps.models import (
    BbpsBillerAdditionalInfoSchema,
    BbpsBillerCcf1Config,
    BbpsBillerInputParam,
    BbpsBillerMaster,
    BbpsBillerPaymentChannelLimit,
    BbpsBillerPaymentModeLimit,
)
from apps.integrations.bbps_client import BBPSClient
from apps.integrations.billavenue.parsers import _get_ci
from apps.integrations.models import BillAvenueAgentProfile, BillAvenueConfig


def _as_bool(v) -> bool:
    return str(v).strip().lower() in ('1', 'true', 'yes', 'y')


def _field_str(raw: dict, name: str) -> str:
    v = _get_ci(raw, name)
    return str(v) if v is not None else ''


def _biller_row_has_id(row: dict) -> bool:
    v = _get_ci(row, 'billerId')
    return bool(str(v or '').strip())


def _coerce_biller_block(v) -> list[dict]:
    if v is None:
        return []
    if isinstance(v, dict):
        return [v] if _biller_row_has_id(v) else []
    if isinstance(v, list):
        return [x for x in v if isinstance(x, dict) and _biller_row_has_id(x)]
    return []


def _scan_biller_lists(node: dict, depth: int = 0) -> list[dict]:
    """Find the largest list of objects that look like biller rows (unusual MDM nesting)."""
    if depth > 8 or not isinstance(node, dict):
        return []
    best: list[dict] = []
    for v in node.values():
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            rows = [x for x in v if _biller_row_has_id(x)]
            if len(rows) > len(best):
                best = list(rows)
        if isinstance(v, dict):
            sub = _scan_biller_lists(v, depth + 1)
            if len(sub) > len(best):
                best = sub
    return best


def _iter_billers(payload, _depth: int = 0) -> list[dict]:
    """Extract biller rows from MDM JSON (camelCase, PascalCase, or single-key XML roots)."""
    if not isinstance(payload, dict) or not payload or _depth > 6:
        return []
    p = payload
    if len(p) == 1:
        inner = next(iter(p.values()))
        if isinstance(inner, dict):
            p = inner

    b = _get_ci(p, 'biller')
    out = _coerce_biller_block(b)
    if out:
        return out

    for wrap in ('billerInfoResponse', 'billerMdmResponse', 'extMdmResponse', 'mdmResponse', 'MdmResponse'):
        node = _get_ci(p, wrap)
        if isinstance(node, dict):
            out = _iter_billers(node, _depth + 1)
            if out:
                return out

    if _depth == 0:
        return _scan_biller_lists(payload)
    return []


def _config_for_sync_client() -> BillAvenueConfig | None:
    return BillAvenueConfig.objects.filter(
        is_active=True, enabled=True, is_deleted=False, mode__in=['uat', 'prod']
    ).first()


def _default_agent_id_for_config(config: BillAvenueConfig | None) -> str:
    if not config:
        return ''
    prof = (
        BillAvenueAgentProfile.objects.filter(config=config, enabled=True, is_deleted=False)
        .order_by('name')
        .first()
    )
    return str(prof.agent_id).strip() if prof else ''


@transaction.atomic
def sync_biller_info(biller_ids: Iterable[str] | None = None) -> dict:
    """Fetch BillAvenue MDM and refresh biller cache tables."""
    biller_ids = [b for b in (biller_ids or []) if b]
    client = BBPSClient()
    cfg = getattr(client, 'config', None) or _config_for_sync_client()
    agent_id = _default_agent_id_for_config(cfg)
    payload: dict = {}
    if agent_id:
        payload['agentId'] = agent_id
    if biller_ids:
        payload['billerId'] = biller_ids
    normalized = client.biller_info(payload)
    billers = _iter_billers(normalized)

    seen = set()
    updated = 0
    for raw in billers:
        if not isinstance(raw, dict):
            continue
        biller_id = _field_str(raw, 'billerId').strip()
        if not biller_id:
            continue
        seen.add(biller_id)
        m, _ = BbpsBillerMaster.objects.update_or_create(
            biller_id=biller_id,
            defaults={
                'biller_name': _field_str(raw, 'billerName'),
                'biller_alias_name': _field_str(raw, 'billerAliasName'),
                'biller_category': _field_str(raw, 'billerCategory'),
                'biller_status': _field_str(raw, 'billerStatus'),
                'biller_adhoc': _as_bool(_get_ci(raw, 'billerAdhoc')),
                'biller_coverage': _field_str(raw, 'billerCoverage'),
                'biller_fetch_requirement': _field_str(raw, 'billerFetchRequiremet'),
                'biller_payment_exactness': _field_str(raw, 'billerPaymentExactness'),
                'biller_support_bill_validation': _field_str(raw, 'billerSupportBillValidation'),
                'support_pending_status': _field_str(raw, 'supportPendingStatus'),
                'support_deemed': _field_str(raw, 'supportDeemed'),
                'biller_timeout': _field_str(raw, 'billerTimeout'),
                'biller_amount_options': _field_str(raw, 'billerAmountOptions'),
                'recharge_amount_in_validation_request': _field_str(raw, 'rechargeAmountInValidationRequest'),
                'plan_mdm_requirement': _field_str(raw, 'planMdmRequirement'),
                'last_synced_at': timezone.now(),
                'sync_error': '',
                'is_stale': False,
                'raw_payload': raw,
            },
        )
        updated += 1

        BbpsBillerInputParam.objects.filter(biller=m).delete()
        params_block = _get_ci(raw, 'billerInputParams') or []
        if isinstance(params_block, dict):
            params_block = [params_block]
        order = 0
        for outer in params_block:
            if not isinstance(outer, dict):
                continue
            p_list = _get_ci(outer, 'paramsList')
            if p_list is None and isinstance(outer, list):
                p_list = outer
            if p_list is None and isinstance(outer, dict):
                p_list = [outer]
            for p in p_list or []:
                if not isinstance(p, dict):
                    continue
                order += 1
                vis = _get_ci(p, 'visibility')
                BbpsBillerInputParam.objects.create(
                    biller=m,
                    param_name=_field_str(p, 'paramName'),
                    data_type=_field_str(p, 'dataType'),
                    is_optional=_as_bool(_get_ci(p, 'isOptional')),
                    min_length=int(str(_get_ci(p, 'minLength') or '0') or 0),
                    max_length=int(str(_get_ci(p, 'maxLength') or '0') or 0),
                    regex=_field_str(p, 'regEx'),
                    visibility=_as_bool(vis if vis is not None else True),
                    display_order=order,
                )

        BbpsBillerPaymentModeLimit.objects.filter(biller=m).delete()
        bpm = _get_ci(raw, 'billerPaymentModes') or {}
        if not isinstance(bpm, dict):
            bpm = {}
        mode_list = _get_ci(bpm, 'paymentModeList') or []
        if not isinstance(mode_list, list):
            mode_list = []
        for it in mode_list:
            if not isinstance(it, dict):
                continue
            BbpsBillerPaymentModeLimit.objects.create(
                biller=m,
                payment_mode=_field_str(it, 'paymentModeName') or _field_str(it, 'paymentMode'),
                min_amount=_field_str(it, 'minAmount') or '0',
                max_amount=_field_str(it, 'maxAmount') or '0',
                is_active=True,
            )

        BbpsBillerPaymentChannelLimit.objects.filter(biller=m).delete()
        ch_outer = _get_ci(raw, 'billerPaymentChannels') or []
        if isinstance(ch_outer, dict):
            ch_outer = [ch_outer]
        if not isinstance(ch_outer, list):
            ch_outer = []
        for outer in ch_outer:
            if not isinstance(outer, dict):
                continue
            pch_list = _get_ci(outer, 'paymentChannelList') or []
            if not isinstance(pch_list, list):
                pch_list = []
            for it in pch_list:
                if not isinstance(it, dict):
                    continue
                BbpsBillerPaymentChannelLimit.objects.create(
                    biller=m,
                    payment_channel=_field_str(it, 'paymentChannelName'),
                    min_amount=_field_str(it, 'minAmount') or '0',
                    max_amount=_field_str(it, 'maxAmount') or '0',
                    is_active=True,
                )

        BbpsBillerAdditionalInfoSchema.objects.filter(biller=m).delete()
        for grp in ('billerAdditionalInfo', 'billerAdditionalInfoPayment', 'planAdditionalInfo'):
            arr = _get_ci(raw, grp) or []
            if isinstance(arr, dict):
                arr = [arr]
            if not isinstance(arr, list):
                continue
            for block in arr:
                if not isinstance(block, dict):
                    continue
                p_list = _get_ci(block, 'paramsList')
                if p_list is None and isinstance(block, dict):
                    p_list = [block]
                if p_list is None:
                    p_list = []
                for p in p_list or []:
                    if not isinstance(p, dict) or not _get_ci(p, 'paramName'):
                        continue
                    opt = _get_ci(p, 'isOptional')
                    BbpsBillerAdditionalInfoSchema.objects.create(
                        biller=m,
                        info_group=grp,
                        info_name=_field_str(p, 'paramName'),
                        data_type=_field_str(p, 'dataType'),
                        is_optional=_as_bool(opt if opt is not None else True),
                    )

        BbpsBillerCcf1Config.objects.filter(biller=m).delete()
        ccf = _get_ci(raw, 'interchangeFeeCCF1') or {}
        if isinstance(ccf, dict) and ccf:
            BbpsBillerCcf1Config.objects.create(
                biller=m,
                fee_code=_field_str(ccf, 'feeCode') or 'CCF1',
                fee_direction=_field_str(ccf, 'feeDirection'),
                flat_fee=_field_str(ccf, 'flatFee') or '0',
                percent_fee=_field_str(ccf, 'percentFee') or '0',
                fee_min_amount=_field_str(ccf, 'feeMinAmt') or '0',
                fee_max_amount=_field_str(ccf, 'feeMaxAmt') or '0',
            )

    if biller_ids:
        BbpsBillerMaster.objects.exclude(biller_id__in=seen).update(is_stale=True)

    sample_categories = sorted(
        list(
            {
                str(_field_str(x, 'billerCategory') or '').strip()
                for x in billers
                if isinstance(x, dict) and str(_field_str(x, 'billerCategory') or '').strip()
            }
        )
    )[:20]
    out: dict = {
        'updated_count': updated,
        'biller_count': len(billers),
        'agent_id_used': agent_id or None,
        'sample_categories': sample_categories,
        'mapping_ready': bool(len(billers) > 0),
    }
    if not billers and isinstance(normalized, dict):
        out['mdm_root_keys'] = sorted([str(k) for k in normalized.keys()])[:40]
        out['normalized_preview'] = {k: type(v).__name__ for k, v in list(normalized.items())[:10]}
    return out
