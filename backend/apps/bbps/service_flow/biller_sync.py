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
from apps.bbps.services import ALLOWED_BILLER_STATUSES
from apps.integrations.bbps_client import BBPSClient
from apps.integrations.billavenue.errors import BillAvenueClientError
from apps.integrations.billavenue.parsers import _get_ci
from apps.integrations.models import BillAvenueAgentProfile, BillAvenueConfig


def _as_bool(v) -> bool:
    return str(v).strip().lower() in ('1', 'true', 'yes', 'y')


def _field_str(raw: dict, name: str) -> str:
    v = _get_ci(raw, name)
    if v is None:
        return ''
    return str(v).replace('\x00', '').strip()


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


def _upsert_governance_rows(mdm_row: dict, biller_master: BbpsBillerMaster) -> dict[str, bool]:
    # Governance catalog (category/provider/map) is intentionally bypassed.
    # Visibility and payment eligibility are driven directly from biller master.
    return {'category_created': False, 'provider_created': False, 'map_created': False}


def _coerce_obj_list(v) -> list[dict]:
    if v is None:
        return []
    if isinstance(v, dict):
        return [v]
    if isinstance(v, list):
        return [x for x in v if isinstance(x, dict)]
    return []


def _extract_param_rows(block) -> list[dict]:
    out: list[dict] = []
    for outer in _coerce_obj_list(block):
        params = (
            _get_ci(outer, 'paramsList')
            or _get_ci(outer, 'paramInfo')
            or _get_ci(outer, 'input')
            or outer
        )
        for row in _coerce_obj_list(params):
            out.append(row)
    return out


def _extract_mode_rows(block) -> list[dict]:
    out: list[dict] = []
    for outer in _coerce_obj_list(block):
        modes = (
            _get_ci(outer, 'paymentModeList')
            or _get_ci(outer, 'paymentModeInfo')
            or outer
        )
        for row in _coerce_obj_list(modes):
            out.append(row)
    return out


def _extract_channel_rows(block) -> list[dict]:
    out: list[dict] = []
    for outer in _coerce_obj_list(block):
        channels = (
            _get_ci(outer, 'paymentChannelList')
            or _get_ci(outer, 'paymentChannelInfo')
            or outer
        )
        for row in _coerce_obj_list(channels):
            out.append(row)
    return out


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
def sync_biller_info(
    biller_ids: Iterable[str] | None = None,
    *,
    request_id: str = '',
) -> dict:
    """Fetch BillAvenue MDM and refresh biller cache tables."""
    biller_ids = [b for b in (biller_ids or []) if b]
    client = BBPSClient()
    cfg = getattr(client, 'config', None) or _config_for_sync_client()
    agent_id = _default_agent_id_for_config(cfg)
    payload: dict = {}
    retry_without_agent_used = False
    upstream_status_code = ''
    sync_warning = ''
    if agent_id:
        payload['agentId'] = agent_id
    if biller_ids:
        # BillAvenue MDM is inconsistent: single biller sometimes works only as scalar.
        payload['billerId'] = biller_ids[0] if len(biller_ids) == 1 else biller_ids
    try:
        normalized = client.biller_info(payload)
    except BillAvenueClientError as exc:
        # Safe fallback for some institutes: retry MDM without agentId when provider returns code=205.
        msg = str(exc or '')
        if 'code=205' in msg and payload.get('agentId'):
            payload_retry = dict(payload)
            payload_retry.pop('agentId', None)
            retry_without_agent_used = True
            normalized = client.biller_info(payload_retry)
        else:
            raise
    if isinstance(normalized, dict):
        upstream_status_code = str(_get_ci(normalized, 'responseCode') or '')
        if upstream_status_code == '205':
            sync_warning = 'BillAvenue returned code 205 (entitlement/profile mismatch).'
    billers = _iter_billers(normalized)

    seen = set()
    updated = 0
    governance_created = {'categories': 0, 'providers': 0, 'maps': 0}
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
                'biller_amount_options': _field_str(raw, 'billerAmountOptions')[:100],
                'recharge_amount_in_validation_request': _field_str(raw, 'rechargeAmountInValidationRequest'),
                'plan_mdm_requirement': _field_str(raw, 'planMdmRequirement'),
                'last_synced_at': timezone.now(),
                'source_type': 'synced',
                'is_active_local': _field_str(raw, 'billerStatus').upper() in ALLOWED_BILLER_STATUSES,
                'last_sync_status': 'success',
                'last_sync_error': '',
                'last_sync_request_id': request_id or '',
                # If a biller was previously soft-deleted/cleared, sync should restore it.
                'is_deleted': False,
                'deleted_at': None,
                'soft_deleted_at': None,
                'sync_error': '',
                'is_stale': False,
                'raw_payload': raw,
            },
        )
        updated += 1
        created_flags = _upsert_governance_rows(raw, m)
        governance_created['categories'] += int(created_flags['category_created'])
        governance_created['providers'] += int(created_flags['provider_created'])
        governance_created['maps'] += int(created_flags['map_created'])

        BbpsBillerInputParam.objects.filter(biller=m).delete()
        params_block = _get_ci(raw, 'billerInputParams') or []
        order = 0
        for p in _extract_param_rows(params_block):
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
        for it in _extract_mode_rows(bpm):
            BbpsBillerPaymentModeLimit.objects.create(
                biller=m,
                payment_mode=_field_str(it, 'paymentModeName') or _field_str(it, 'paymentMode'),
                min_amount=_field_str(it, 'minAmount') or '0',
                max_amount=_field_str(it, 'maxAmount') or '0',
                is_active=True,
            )

        BbpsBillerPaymentChannelLimit.objects.filter(biller=m).delete()
        ch_outer = _get_ci(raw, 'billerPaymentChannels') or []
        for it in _extract_channel_rows(ch_outer):
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
        'retry_without_agent_used': retry_without_agent_used,
        'upstream_status_code': upstream_status_code,
        'sample_categories': sample_categories,
        'mapping_ready': bool(len(billers) > 0),
        'governance_created': governance_created,
    }
    if sync_warning:
        out['warning'] = sync_warning
    if not billers and isinstance(normalized, dict):
        out['mdm_root_keys'] = sorted([str(k) for k in normalized.keys()])[:40]
        out['normalized_preview'] = {k: type(v).__name__ for k, v in list(normalized.items())[:10]}
    return out
