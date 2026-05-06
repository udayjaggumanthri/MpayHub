"""Persist one MDM biller row → Postgres catalog projections (master + child tables)."""

from __future__ import annotations

from django.utils import timezone

from apps.bbps.catalog.mdm_parse import (
    extract_channel_rows,
    extract_mode_rows,
    extract_param_rows,
    mdm_as_bool,
    mdm_field_str,
)
from apps.bbps.mdm_param_utils import extract_param_lov_and_extras
from apps.bbps.models import (
    BbpsBillerAdditionalInfoSchema,
    BbpsBillerCcf1Config,
    BbpsBillerInputParam,
    BbpsBillerMaster,
    BbpsBillerPaymentChannelLimit,
    BbpsBillerPaymentModeLimit,
)
from apps.bbps.services import ALLOWED_BILLER_STATUSES
from apps.bbps.service_flow.payment_ui_policy import maybe_add_implicit_cash_payment_mode
from apps.bbps.service_flow.provider_policy import bootstrap_default_biller_policy_if_missing
from apps.integrations.billavenue.parsers import _get_ci


def upsert_governance_rows(mdm_row: dict, biller_master: BbpsBillerMaster) -> dict[str, bool]:
    """Governance catalog bypass placeholder — visibility driven from biller master."""
    return {'category_created': False, 'provider_created': False, 'map_created': False}


def persist_biller_from_mdm_row(raw: dict, *, request_id: str = '') -> tuple[BbpsBillerMaster, dict[str, int]]:
    """
    Upsert ``BbpsBillerMaster`` and replace dependent rows for a single MDM biller dict.

    Returns ``(master, governance_created_counts)``.
    """
    biller_id = mdm_field_str(raw, 'billerId').strip()
    if not biller_id:
        raise ValueError('MDM row missing billerId')

    m, _ = BbpsBillerMaster.objects.update_or_create(
        biller_id=biller_id,
        defaults={
            'biller_name': mdm_field_str(raw, 'billerName'),
            'biller_alias_name': mdm_field_str(raw, 'billerAliasName'),
            'biller_category': mdm_field_str(raw, 'billerCategory'),
            'biller_status': mdm_field_str(raw, 'billerStatus'),
            'biller_adhoc': mdm_as_bool(_get_ci(raw, 'billerAdhoc')),
            'biller_coverage': mdm_field_str(raw, 'billerCoverage'),
            'biller_fetch_requirement': mdm_field_str(raw, 'billerFetchRequiremet'),
            'biller_payment_exactness': mdm_field_str(raw, 'billerPaymentExactness'),
            'biller_support_bill_validation': mdm_field_str(raw, 'billerSupportBillValidation'),
            'support_pending_status': mdm_field_str(raw, 'supportPendingStatus'),
            'support_deemed': mdm_field_str(raw, 'supportDeemed'),
            'biller_timeout': mdm_field_str(raw, 'billerTimeout'),
            'biller_amount_options': mdm_field_str(raw, 'billerAmountOptions')[:100],
            'recharge_amount_in_validation_request': mdm_field_str(raw, 'rechargeAmountInValidationRequest'),
            'plan_mdm_requirement': mdm_field_str(raw, 'planMdmRequirement'),
            'last_synced_at': timezone.now(),
            'source_type': 'synced',
            'is_active_local': mdm_field_str(raw, 'billerStatus').upper() in ALLOWED_BILLER_STATUSES,
            'last_sync_status': 'success',
            'last_sync_error': '',
            'last_sync_request_id': request_id or '',
            'is_deleted': False,
            'deleted_at': None,
            'soft_deleted_at': None,
            'sync_error': '',
            'is_stale': False,
            'raw_payload': raw,
        },
    )

    created_flags = upsert_governance_rows(raw, m)
    governance_created = {
        'categories': int(created_flags['category_created']),
        'providers': int(created_flags['provider_created']),
        'maps': int(created_flags['map_created']),
    }

    BbpsBillerInputParam.objects.filter(biller=m).delete()
    params_block = _get_ci(raw, 'billerInputParams') or []
    order = 0
    for p in extract_param_rows(params_block):
        order += 1
        vis = _get_ci(p, 'visibility')
        lov_rows, mdm_extras = extract_param_lov_and_extras(p if isinstance(p, dict) else {})
        BbpsBillerInputParam.objects.create(
            biller=m,
            param_name=mdm_field_str(p, 'paramName'),
            data_type=mdm_field_str(p, 'dataType'),
            is_optional=mdm_as_bool(_get_ci(p, 'isOptional')),
            min_length=int(str(_get_ci(p, 'minLength') or '0') or 0),
            max_length=int(str(_get_ci(p, 'maxLength') or '0') or 0),
            regex=mdm_field_str(p, 'regEx'),
            visibility=mdm_as_bool(vis if vis is not None else True),
            display_order=order,
            default_values=lov_rows,
            mdm_extras=mdm_extras,
        )

    BbpsBillerPaymentModeLimit.objects.filter(biller=m).delete()
    bpm = _get_ci(raw, 'billerPaymentModes') or {}
    for it in extract_mode_rows(bpm):
        BbpsBillerPaymentModeLimit.objects.create(
            biller=m,
            payment_mode=mdm_field_str(it, 'paymentModeName') or mdm_field_str(it, 'paymentMode'),
            min_amount=mdm_field_str(it, 'minAmount') or '0',
            max_amount=mdm_field_str(it, 'maxAmount') or '0',
            is_active=True,
        )

    BbpsBillerPaymentChannelLimit.objects.filter(biller=m).delete()
    ch_outer = _get_ci(raw, 'billerPaymentChannels') or []
    for it in extract_channel_rows(ch_outer):
        BbpsBillerPaymentChannelLimit.objects.create(
            biller=m,
            payment_channel=mdm_field_str(it, 'paymentChannelName'),
            min_amount=mdm_field_str(it, 'minAmount') or '0',
            max_amount=mdm_field_str(it, 'maxAmount') or '0',
            is_active=True,
        )

    mode_labels_sync = [
        str(mdm_field_str(it, 'paymentModeName') or mdm_field_str(it, 'paymentMode') or '').strip()
        for it in extract_mode_rows(bpm)
        if str(mdm_field_str(it, 'paymentModeName') or mdm_field_str(it, 'paymentMode') or '').strip()
    ]
    ch_codes_sync = [
        str(mdm_field_str(it, 'paymentChannelName') or '').strip().upper()
        for it in extract_channel_rows(ch_outer)
        if str(mdm_field_str(it, 'paymentChannelName') or '').strip()
    ]
    maybe_add_implicit_cash_payment_mode(m, channel_codes_upper=ch_codes_sync, mdm_mode_labels=mode_labels_sync)
    bootstrap_default_biller_policy_if_missing(biller=m)

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
                    info_name=mdm_field_str(p, 'paramName'),
                    data_type=mdm_field_str(p, 'dataType'),
                    is_optional=mdm_as_bool(opt if opt is not None else True),
                )

    BbpsBillerCcf1Config.objects.filter(biller=m).delete()
    ccf = _get_ci(raw, 'interchangeFeeCCF1') or {}
    if isinstance(ccf, dict) and ccf:
        BbpsBillerCcf1Config.objects.create(
            biller=m,
            fee_code=mdm_field_str(ccf, 'feeCode') or 'CCF1',
            fee_direction=mdm_field_str(ccf, 'feeDirection'),
            flat_fee=mdm_field_str(ccf, 'flatFee') or '0',
            percent_fee=mdm_field_str(ccf, 'percentFee') or '0',
            fee_min_amount=mdm_field_str(ccf, 'feeMinAmt') or '0',
            fee_max_amount=mdm_field_str(ccf, 'feeMaxAmt') or '0',
        )

    return m, governance_created


def mark_unseen_billers_stale(requested_ids: list[str], seen_ids: set[str]) -> None:
    if requested_ids:
        BbpsBillerMaster.objects.exclude(biller_id__in=seen_ids).update(is_stale=True)
