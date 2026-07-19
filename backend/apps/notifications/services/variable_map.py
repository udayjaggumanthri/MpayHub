"""
Map domain SMS context keys to MSG91 Flow recipient variables.

MSG91 Flow expects recipient object keys to match template placeholders exactly:
  ##amount##           → send {"amount": "..."}
  ##transaction_id##   → send {"transaction_id": "..."}
  ##var1## / ##var2##  → send {"var1": "...", "var2": "..."}
"""
from __future__ import annotations

import re
from typing import Any

_VARN = re.compile(r'^var\d+$', re.IGNORECASE)


def map_targets_are_only_varn(variable_map: dict[str, Any] | None) -> bool:
    """True when every mapped MSG91 key looks like var1, var2, …"""
    vmap = variable_map if isinstance(variable_map, dict) else {}
    values = [str(v).strip() for v in vmap.values() if v is not None and str(v).strip()]
    if not values:
        return False
    return all(_VARN.fullmatch(v) for v in values)


def apply_variable_map(
    context: dict[str, Any] | None,
    variable_map: dict[str, Any] | None,
) -> dict[str, str]:
    """
    Convert semantic context into MSG91 recipient fields.

    If variable_map is empty, pass context keys through unchanged (backward compatible).
    If mapped, only mapped keys are sent (values as strings).
    """
    ctx = context or {}
    vmap = variable_map if isinstance(variable_map, dict) else {}
    if not vmap:
        return {str(k): str(v) for k, v in ctx.items() if v is not None}

    out: dict[str, str] = {}
    for app_key, msg91_key in vmap.items():
        if not app_key or not msg91_key:
            continue
        if app_key not in ctx or ctx[app_key] is None:
            continue
        out[str(msg91_key).strip()] = str(ctx[app_key])
    return out
