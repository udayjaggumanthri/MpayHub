"""
Pure MDM parsing: normalized BillAvenue payload → biller row dicts and nested fragments.
No database access.
"""

from __future__ import annotations

from apps.integrations.billavenue.parsers import _get_ci


def mdm_as_bool(v) -> bool:
    return str(v).strip().lower() in ('1', 'true', 'yes', 'y')


def mdm_field_str(raw: dict, name: str) -> str:
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


def iter_billers_from_payload(payload, _depth: int = 0) -> list[dict]:
    """
    Extract biller rows from MDM JSON (camelCase, PascalCase, or single-key XML roots).

    Backward-compatible with legacy ``_iter_billers`` behavior.
    """
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
            out = iter_billers_from_payload(node, _depth + 1)
            if out:
                return out

    if _depth == 0:
        return _scan_biller_lists(payload)
    return []


def _coerce_obj_list(v) -> list[dict]:
    if v is None:
        return []
    if isinstance(v, dict):
        return [v]
    if isinstance(v, list):
        return [x for x in v if isinstance(x, dict)]
    return []


def extract_param_rows(block) -> list[dict]:
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


def extract_mode_rows(block) -> list[dict]:
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


def extract_channel_rows(block) -> list[dict]:
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


def upstream_response_code(normalized: dict | None) -> str:
    if not isinstance(normalized, dict):
        return ''
    return str(_get_ci(normalized, 'responseCode') or '')
