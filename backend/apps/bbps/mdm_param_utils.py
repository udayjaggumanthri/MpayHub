"""Normalize BillAvenue MDM billerInputParams rows for persistence and schema API."""

from __future__ import annotations

from typing import Any

from apps.integrations.billavenue.parsers import _get_ci


def _field_str(raw: dict, name: str) -> str:
    v = _get_ci(raw, name)
    if v is None:
        return ''
    return str(v).replace('\x00', '').strip()


def extract_param_lov_and_extras(param_row: dict) -> tuple[list, dict]:
    """
    Build default_values (UI choices) and mdm_extras (help text, raw fragments)
    from a single MDM paramsList row.
    """
    extras: dict[str, Any] = {}
    choices: list = []

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
    ):
        block = _get_ci(param_row, key)
        if block is None:
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
                    choices.append({'value': str(item), 'label': str(item)})
        if choices:
            extras['lov_source_key'] = key
            break

    if not choices:
        dv = _get_ci(param_row, 'defaultValues') or _get_ci(param_row, 'DefaultValues')
        if isinstance(dv, list):
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
