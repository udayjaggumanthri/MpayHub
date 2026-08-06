"""Normalize BillAvenue MDM billerInputParams rows for persistence and schema API."""

from __future__ import annotations

from typing import Any

import re

from apps.integrations.billavenue.parsers import _get_ci


_PLACEHOLDER_PARAM_NAME = re.compile(r'^([a-zA-Z])( [a-zA-Z]){0,7}$')


def is_placeholder_style_param_name(name: str) -> bool:
    """True for NPCI/BillAvenue test billers that ship meaningless paramName tokens (``a``, ``a b``, …)."""
    t = str(name or '').strip()
    if not t:
        return True
    if len(t) == 1 and t.isalpha():
        return True
    return bool(_PLACEHOLDER_PARAM_NAME.match(t))


def input_schema_display_label(
    *,
    wire: str,
    help_text: str,
    extras: dict[str, Any],
    order: int,
    raw_row: dict | None,
) -> str:
    """Human-readable label for pay UI. ``wire`` is the stored MDM token sent as-is to BillAvenue."""
    ex = extras if isinstance(extras, dict) else {}
    dl = str(ex.get('display_label') or '').strip()
    if dl:
        return dl[:200]
    if raw_row and isinstance(raw_row, dict):
        _, ex2 = extract_param_lov_and_extras(raw_row)
        dl2 = str(ex2.get('display_label') or '').strip()
        if dl2:
            return dl2[:200]
    ht = str(help_text or '').strip()
    wire_s = str(wire or '').strip()
    if ht and len(ht) >= 4 and ht.lower() != wire_s.lower():
        return ht[:200]
    if is_placeholder_style_param_name(wire_s):
        return f'Bill reference detail {order}'
    return (wire_s.replace('_', ' ').replace('-', ' ') or f'Field {order}')


def _field_str(raw: dict, name: str) -> str:
    v = _get_ci(raw, name)
    if v is None:
        return ''
    return str(v).replace('\x00', '').strip()


def mdm_input_param_wire_name(param_row: dict) -> str:
    """
    BillAvenue / NPCI wire key for inputParams (must match MDM when calling fetch/pay).

    Some payloads use synonyms; we still persist a single canonical ``param_name`` column.
    """
    if not isinstance(param_row, dict):
        return ''
    return (
        _field_str(param_row, 'paramName')
        or _field_str(param_row, 'parameterName')
        or _field_str(param_row, 'customerParamName')
        or _field_str(param_row, 'fieldName')
        or _field_str(param_row, 'name')
    ).strip()


_CSV_SPLIT_RE = re.compile(r'[,|;]')
# Pure LOV-style regex: ^(Token)$|^(Token 2)$|...
_REGEX_ALT_TOKEN_RE = re.compile(r'\^\(([^)]+)\)\$')


def _choices_from_delimited_string(raw: str) -> list[dict]:
    """Split BillAvenue comma/pipe/semicolon value lists into schema choices."""
    out: list[dict] = []
    seen: set[str] = set()
    for tok in _CSV_SPLIT_RE.split(str(raw or '')):
        val = tok.strip()
        if not val or val in seen:
            continue
        seen.add(val)
        out.append({'value': val, 'label': val})
    return out


def _choices_from_regex_alternation(regex: str) -> list[dict]:
    """
    When MDM only ships LOV inside regEx as ^(A)$|^(B)$|..., extract tokens as choices.
    Skip patterns that look like character classes or free-form validation (e.g. ^[6-9]).
    """
    rx = str(regex or '').strip()
    if not rx or '[' in rx or '{' in rx or '*' in rx or '+' in rx or '?' in rx:
        return []
    tokens = _REGEX_ALT_TOKEN_RE.findall(rx)
    if len(tokens) < 2:
        return []
    # Require the whole pattern to be only these alternations (optional outer grouping).
    rebuilt = '|'.join(f'^({t})$' for t in tokens)
    compact = re.sub(r'\s+', '', rx)
    rebuilt_c = re.sub(r'\s+', '', rebuilt)
    if compact != rebuilt_c and compact != f'({rebuilt_c})':
        # Allow missing outer grouping; still accept if every ^(...) $ appears in order
        if not all(f'^({t})$' in rx or f'^({t})$' in compact for t in tokens):
            return []
    out: list[dict] = []
    seen: set[str] = set()
    for t in tokens:
        val = str(t).strip()
        if not val or val in seen:
            continue
        seen.add(val)
        out.append({'value': val, 'label': val})
    return out


def extract_param_lov_and_extras(param_row: dict) -> tuple[list, dict]:
    """
    Build default_values (UI choices) and mdm_extras (help text, raw fragments)
    from a single MDM paramsList row.
    """
    extras: dict[str, Any] = {}
    choices: list = []

    display_label = (
        _field_str(param_row, 'paramLabel')
        or _field_str(param_row, 'paramDisplayName')
        or _field_str(param_row, 'displayName')
        or _field_str(param_row, 'label')
        or _field_str(param_row, 'paramDescription')
        or _field_str(param_row, 'description')
    )
    if display_label:
        extras['display_label'] = display_label[:200]

    for key in (
        'listOfValues',
        'ListOfValues',
        'valuesList',
        'ValuesList',
        'valueList',
        'ValueList',
        'lovList',
        'LOVList',
        'enumValues',
        'EnumValues',
        'values',
        'Values',
        'paramValues',
        'ParamValues',
    ):
        block = _get_ci(param_row, key)
        if block is None:
            continue
        if isinstance(block, str):
            choices = _choices_from_delimited_string(block)
            if choices:
                extras['lov_source_key'] = key
                break
            continue
        if isinstance(block, dict):
            block = [block]
        if isinstance(block, list):
            for item in block:
                if isinstance(item, dict):
                    val = (
                        _field_str(item, 'value')
                        or _field_str(item, 'paramValue')
                        or _field_str(item, 'code')
                    )
                    label = (
                        _field_str(item, 'displayName')
                        or _field_str(item, 'name')
                        or _field_str(item, 'label')
                        or val
                    )
                    if val:
                        choices.append({'value': val, 'label': label or val})
                elif item not in (None, ''):
                    # String entries may themselves be CSV blobs
                    s = str(item).strip()
                    if ',' in s or '|' in s or ';' in s:
                        choices.extend(_choices_from_delimited_string(s))
                    else:
                        choices.append({'value': s, 'label': s})
        if choices:
            extras['lov_source_key'] = key
            break

    if not choices:
        dv = _get_ci(param_row, 'defaultValues') or _get_ci(param_row, 'DefaultValues')
        if isinstance(dv, str):
            choices = _choices_from_delimited_string(dv)
        elif isinstance(dv, list):
            for item in dv:
                if isinstance(item, dict):
                    val = _field_str(item, 'value') or _field_str(item, 'paramValue')
                    if val:
                        choices.append(
                            {
                                'value': val,
                                'label': _field_str(item, 'displayName') or _field_str(item, 'label') or val,
                            }
                        )
                elif item not in (None, ''):
                    choices.append({'value': str(item), 'label': str(item)})

    if not choices:
        rx = (
            _field_str(param_row, 'regEx')
            or _field_str(param_row, 'regex')
            or _field_str(param_row, 'RegEx')
        )
        alt = _choices_from_regex_alternation(rx)
        if alt:
            choices = alt
            extras['lov_source_key'] = 'regEx'

    help_text = (
        _field_str(param_row, 'paramHelpText')
        or _field_str(param_row, 'ParamHelpText')
        or _field_str(param_row, 'helpText')
        or _field_str(param_row, 'description')
        or _field_str(param_row, 'paramDescription')
    )
    if help_text:
        extras['help_text'] = help_text

    return choices, extras


def infer_input_kind(*, data_type: str, choices: list) -> str:
    if choices:
        return 'select'
    dt = str(data_type or '').strip().upper()
    if 'ALPHANUMERIC' in dt or 'ALPHA' in dt:
        return 'text'
    if any(x in dt for x in ('NUMERIC', 'DECIMAL', 'NUMBER', 'AMOUNT', 'INTEGER')):
        return 'numeric'
    if 'DATE' in dt and 'UPDATE' not in dt:
        return 'date'
    return 'text'


def constraints_hint_for_schema_row(
    *,
    min_length: int,
    max_length: int,
    data_type: str,
    regex: str,
    input_kind: str,
) -> str:
    """Short human-readable rules for the pay UI (BillAvenue MDM limits)."""
    parts: list[str] = []
    dt = str(data_type or '').strip()
    if dt:
        parts.append(f'MDM type: {dt}')
    mn = int(min_length or 0)
    mx = int(max_length or 0)
    if mn > 0 and mx > 0:
        parts.append(f'{mn}–{mx} characters')
    elif mn > 0:
        parts.append(f'at least {mn} characters')
    elif mx > 0:
        parts.append(f'at most {mx} characters')
    if str(regex or '').strip():
        parts.append('must match biller pattern')
    if input_kind == 'numeric':
        parts.append('digits only')
    return ' · '.join(parts)


def normalize_schema_choices(default_values: list | None) -> list[dict]:
    """Return [{value, label}, ...] for API consumers."""
    out: list[dict] = []
    if not isinstance(default_values, list):
        return out
    for item in default_values:
        if isinstance(item, dict) and (item.get('value') or item.get('paramValue')):
            v = str(item.get('value') or item.get('paramValue') or '').strip()
            lab = str(item.get('label') or item.get('displayName') or item.get('name') or v).strip()
            if v:
                out.append({'value': v, 'label': lab or v})
        elif item not in (None, ''):
            s = str(item).strip()
            if s:
                out.append({'value': s, 'label': s})
    return out
