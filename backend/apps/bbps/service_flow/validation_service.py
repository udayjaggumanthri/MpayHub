from __future__ import annotations

import re
from typing import Any

from apps.bbps.catalog.env import get_biller_master
from apps.bbps.models import BbpsBillerInputParam
from apps.core.exceptions import TransactionFailed
from apps.integrations.bbps_client import BBPSClient


class BbpsInputValidationError(Exception):
    """Raised when MDM input validation fails before calling BillAvenue."""

    def __init__(self, message: str, *, field_errors: list[dict] | None = None):
        super().__init__(message)
        self.field_errors = list(field_errors or [])


def _plan_mdm_enabled(biller) -> bool:
    req = str(getattr(biller, 'plan_mdm_requirement', '') or '').strip().upper()
    return req in ('MANDATORY', 'OPTIONAL', 'SUPPORTED', 'Y', 'YES', 'TRUE', '1')


def _plan_id_param_name(biller_id: str) -> str:
    """MDM wire name used for plan selection (BSNL prepaid uses hidden ``Id``)."""
    master = get_biller_master(biller_id)
    qs = BbpsBillerInputParam.objects.filter(
        is_deleted=False,
        biller__is_deleted=False,
        biller__biller_id=biller_id,
    )
    if master is not None:
        qs = qs.filter(biller_id=master.pk)
    # Prefer exact "Id", then any visibility=false required alphanumeric param.
    for p in qs.order_by('display_order', 'id'):
        if str(p.param_name or '').strip().lower() == 'id':
            return str(p.param_name).strip()
    for p in qs.order_by('display_order', 'id'):
        if not bool(getattr(p, 'visibility', True)) and not bool(getattr(p, 'is_optional', True)):
            return str(p.param_name or '').strip()
    return 'Id'


def inject_plan_id_into_input_map(*, biller_id: str, input_map: dict, plan_id: str) -> dict:
    """Copy selected plan into the MDM plan/Id slot before validate/pay."""
    out = dict(input_map or {})
    pid = str(plan_id or '').strip()
    if not pid:
        return out
    key = _plan_id_param_name(biller_id)
    if key:
        out[key] = pid
    return out


def inject_plan_id_into_wire_list(*, biller_id: str, wire: list, plan_id: str) -> list:
    pid = str(plan_id or '').strip()
    rows = [dict(r) for r in (wire or []) if isinstance(r, dict)]
    if not pid:
        return rows
    key = _plan_id_param_name(biller_id)
    if not key:
        return rows
    found = False
    for row in rows:
        name = str(row.get('paramName') or row.get('param_name') or '').strip()
        if name.lower() == key.lower():
            row['paramName'] = key
            row['paramValue'] = pid
            found = True
            break
    if not found:
        rows.append({'paramName': key, 'paramValue': pid})
    return rows


def _norm_key(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', str(name or '').strip().lower())


def _lookup_value(input_map: dict, param_name: str) -> Any:
    if not isinstance(input_map, dict):
        return None
    if param_name in input_map:
        return input_map.get(param_name)
    target = _norm_key(param_name)
    for k, v in input_map.items():
        if _norm_key(str(k)) == target:
            return v
    return None


def _safe_regex(pattern: str):
    try:
        return re.compile(str(pattern))
    except re.error:
        return None


def validate_biller_inputs(*, biller_id: str, input_map: dict, plan_id: str = '') -> list[dict]:
    """
    Enforce MDM input rules before any BillAvenue call.

    Returns wire-ready [{'paramName','paramValue'}, ...] on success.
    Raises BbpsInputValidationError with field_errors on failure.
    """
    master = get_biller_master(biller_id)
    plan_enabled = _plan_mdm_enabled(master)
    plan_slot = _plan_id_param_name(biller_id) if plan_enabled else ''
    # When plan MDM supplies the plan, inject into the MDM Id/plan slot and skip field regex
    # (BillAvenue planIds often do not match the account-Id regex).
    working_map = (
        inject_plan_id_into_input_map(
            biller_id=biller_id, input_map=input_map or {}, plan_id=plan_id
        )
        if (plan_enabled and str(plan_id or '').strip())
        else dict(input_map or {})
    )

    params_qs = BbpsBillerInputParam.objects.filter(
        is_deleted=False,
        biller__is_deleted=False,
        biller__biller_id=biller_id,
    )
    if master is not None:
        params_qs = params_qs.filter(biller_id=master.pk)
    params = list(params_qs.order_by('display_order', 'id'))

    field_errors: list[dict] = []
    known_norm = {_norm_key(p.param_name): p for p in params if p.param_name}

    # Reject unknown submitted names (exact / normalized mismatch vs MDM).
    if params and isinstance(working_map, dict):
        for submitted in working_map.keys():
            nk = _norm_key(str(submitted))
            if nk and nk not in known_norm:
                expected = ', '.join(p.param_name for p in params[:8])
                more = '' if len(params) <= 8 else f' (+{len(params) - 8} more)'
                field_errors.append(
                    {
                        'param': str(submitted),
                        'code': 'E135',
                        'message': (
                            f'Field "{submitted}" is not recognized for this biller. '
                            f'Expected: {expected}{more}'
                        ),
                    }
                )

    resolved: dict[str, str] = {}
    for p in params:
        wire = str(p.param_name or '').strip()
        if not wire:
            continue
        raw = _lookup_value(working_map or {}, wire)
        val = '' if raw in (None,) else str(raw).strip()
        label = wire
        is_plan_slot = bool(plan_slot) and wire.lower() == plan_slot.lower() and str(plan_id or '').strip()

        # Plan-driven Id: accept injected plan_id without MDM account-Id regex.
        if is_plan_slot:
            resolved[wire] = str(plan_id).strip()
            continue

        # Optional + hidden: omit when blank.
        if not bool(getattr(p, 'visibility', True)) and bool(getattr(p, 'is_optional', True)):
            if val:
                resolved[wire] = val
            continue

        # Required + hidden + plan MDM: filled by plan picker, not free-text.
        if (
            not bool(getattr(p, 'visibility', True))
            and not bool(getattr(p, 'is_optional', True))
            and plan_enabled
            and wire.lower() == (plan_slot or '').lower()
        ):
            if not val:
                field_errors.append(
                    {
                        'param': wire,
                        'code': 'RPD053',
                        'message': 'Please select a plan before continuing.',
                    }
                )
            else:
                resolved[wire] = val
            continue

        if not p.is_optional and not val:
            field_errors.append(
                {
                    'param': wire,
                    'code': 'VE008',
                    'message': f'{label} is required.',
                }
            )
            continue

        if not val:
            continue

        mn = int(getattr(p, 'min_length', 0) or 0)
        mx = int(getattr(p, 'max_length', 0) or 0)
        if mn > 0 and len(val) < mn:
            field_errors.append(
                {
                    'param': wire,
                    'code': 'VE009',
                    'message': f'{label} must be at least {mn} characters.',
                }
            )
        if mx > 0 and len(val) > mx:
            field_errors.append(
                {
                    'param': wire,
                    'code': 'VE010',
                    'message': f'{label} must be at most {mx} characters.',
                }
            )

        dt = str(getattr(p, 'data_type', '') or '').strip().upper()
        if any(x in dt for x in ('NUMERIC', 'DECIMAL', 'NUMBER', 'INTEGER')) and 'ALPHA' not in dt:
            if not re.fullmatch(r'[0-9]+([.][0-9]+)?', val):
                field_errors.append(
                    {
                        'param': wire,
                        'code': 'VE011',
                        'message': f'{label} must be numeric.',
                    }
                )

        rx = str(getattr(p, 'regex', '') or '').strip()
        if rx:
            compiled = _safe_regex(rx)
            if compiled is not None:
                ok = bool(compiled.fullmatch(val)) if (rx.startswith('^') or rx.endswith('$')) else bool(
                    compiled.fullmatch(val) or compiled.search(val)
                )
                if not ok:
                    field_errors.append(
                        {
                            'param': wire,
                            'code': 'VE012',
                            'message': f'{label} format is invalid.',
                        }
                    )

        resolved[wire] = val

    if field_errors:
        seen = set()
        unique = []
        for fe in field_errors:
            key = (fe.get('param'), fe.get('code'), fe.get('message'))
            if key in seen:
                continue
            seen.add(key)
            unique.append(fe)
        raise BbpsInputValidationError(
            'Check the highlighted fields — a required detail is missing or does not match what this biller expects.',
            field_errors=unique,
        )

    # If MDM has no params yet, fall back to submitted map (legacy / empty catalog).
    if not params and isinstance(working_map, dict):
        return [
            {'paramName': str(k), 'paramValue': str(v)}
            for k, v in working_map.items()
            if k and v not in (None, '')
        ]

    return [{'paramName': k, 'paramValue': v} for k, v in resolved.items()]


def validate_bill_account(
    *,
    biller_id: str,
    agent_id: str,
    input_params: list,
    customer_info: dict | None = None,
    agent_device_info: dict | None = None,
    plan_id: str = '',
) -> dict:
    biller = get_biller_master(biller_id)
    flag = str((biller.biller_support_bill_validation if biller else '') or '').strip().upper()
    if flag in ('', 'NOT_SUPPORTED', 'UNSUPPORTED'):
        return {'skipped': True, 'reason': 'validation_not_supported', 'response_code': '000'}

    if not str(agent_id or '').strip():
        raise TransactionFailed('Agent ID is required for bill validation. Configure it in BillAvenue Settings.')

    wire = inject_plan_id_into_wire_list(
        biller_id=biller_id,
        wire=input_params if isinstance(input_params, list) else [],
        plan_id=plan_id,
    )
    client = BBPSClient()
    payload = {
        'agentId': str(agent_id).strip(),
        'billerId': biller_id,
        'inputParams': {'input': wire},
    }
    pid = str(plan_id or '').strip()
    if pid:
        payload['planId'] = pid
    if isinstance(customer_info, dict) and customer_info:
        payload['customerInfo'] = customer_info
    if isinstance(agent_device_info, dict) and agent_device_info:
        payload['agentDeviceInfo'] = agent_device_info

    normalized = client.validate_bill(payload)
    nested = normalized.get('billValidationResponse') if isinstance(normalized, dict) else None
    resp_code = str(
        (normalized or {}).get('responseCode')
        or (nested or {}).get('responseCode')
        or '000'
    )
    if str(resp_code) not in ('000', '0') and flag == 'MANDATORY':
        err = ''
        try:
            err_info = (nested or normalized or {}).get('errorInfo') or {}
            err_obj = (err_info.get('error') if isinstance(err_info, dict) else None) or {}
            if isinstance(err_obj, dict):
                err = str(err_obj.get('errorMessage') or err_obj.get('errorCode') or '').strip()
            if not err:
                err = str(
                    (nested or normalized or {}).get('complianceReason')
                    or (nested or normalized or {}).get('complianceCode')
                    or ''
                ).strip()
        except Exception:
            err = ''
        raise TransactionFailed(
            err or f'Bill validation failed for biller={biller_id} (responseCode={resp_code})'
        )
    return {'response': normalized, 'response_code': resp_code, 'skipped': False}
