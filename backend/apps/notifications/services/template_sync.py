"""
MSG91 template sync — single source of truth for placeholder detection + variable maps.

Workflow (loosely coupled):
  domain code  →  semantic context keys (amount, txn_ref, …)
  catalog      →  event_key + variable_schema (what the app can supply)
  MSG91 fetch  →  detected placeholders from live template body (##var1## / ##amount##)
  sync service →  variable_map (app key → MSG91 recipient key)
  dispatch     →  apply_variable_map(context, variable_map) → Flow API

When MSG91 changes a template, admin re-fetches; map is recomputed from detected vars.
Manual overrides are allowed but marked mapping_source=manual until next auto-sync.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.utils import timezone

from apps.notifications.providers.msg91 import extract_msg91_vars, suggest_variable_map


MAPPING_SOURCE_AUTO = 'auto'
MAPPING_SOURCE_MANUAL = 'manual'
MAPPING_SOURCE_DEFAULT = 'default'


@dataclass
class TemplateSyncResult:
    detected_vars: list[str] = field(default_factory=list)
    variable_map: dict[str, str] = field(default_factory=dict)
    unmapped_required: list[str] = field(default_factory=list)
    unused_placeholders: list[str] = field(default_factory=list)
    template_name: str = ''
    template_body: str = ''
    sender_id: str = ''
    dlt_id: str = ''


def required_schema_names(schema: list[dict] | None) -> list[str]:
    names: list[str] = []
    for row in schema or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get('name') or '').strip()
        if not name:
            continue
        if row.get('required', True):
            names.append(name)
    return names


def build_sync_result(
    *,
    schema: list[dict] | None,
    template_body: str = '',
    detected_vars: list[str] | None = None,
    template_name: str = '',
    sender_id: str = '',
    dlt_id: str = '',
) -> TemplateSyncResult:
    """Pure function: schema + MSG91 body/vars → suggested map + diagnostics."""
    body = template_body or ''
    detected = list(detected_vars) if detected_vars is not None else extract_msg91_vars(body)
    vmap = suggest_variable_map(schema, detected)
    required = required_schema_names(schema)
    unmapped = [n for n in required if n not in vmap or not vmap.get(n)]
    used = set(vmap.values())
    unused = [d for d in detected if d not in used]
    return TemplateSyncResult(
        detected_vars=detected,
        variable_map=vmap,
        unmapped_required=unmapped,
        unused_placeholders=unused,
        template_name=template_name or '',
        template_body=body,
        sender_id=sender_id or '',
        dlt_id=dlt_id or '',
    )


def apply_msg91_primary_to_template(template, primary: dict[str, Any] | None) -> TemplateSyncResult:
    """
    Persist MSG91 metadata + auto variable_map onto SmsNotificationTemplate.

    Source of truth for placeholders is the fetched MSG91 template body.
    """
    primary = primary if isinstance(primary, dict) else {}
    body = str(primary.get('template_data') or '')
    detected = primary.get('detected_vars')
    if not isinstance(detected, list) or not detected:
        detected = extract_msg91_vars(body)

    result = build_sync_result(
        schema=getattr(template, 'variable_schema', None) or [],
        template_body=body,
        detected_vars=detected,
        template_name=str(primary.get('template_name') or ''),
        sender_id=str(primary.get('sender_id') or ''),
        dlt_id=str(primary.get('dlt_id') or ''),
    )

    template.msg91_template_name = result.template_name[:200]
    template.msg91_template_body = result.template_body
    template.msg91_detected_vars = list(result.detected_vars)
    template.msg91_sender_id = result.sender_id[:32]
    template.msg91_dlt_id = result.dlt_id[:64]
    template.msg91_synced_at = timezone.now()
    template.variable_map = dict(result.variable_map)
    template.mapping_source = MAPPING_SOURCE_AUTO
    template.save(
        update_fields=[
            'msg91_template_name',
            'msg91_template_body',
            'msg91_detected_vars',
            'msg91_sender_id',
            'msg91_dlt_id',
            'msg91_synced_at',
            'variable_map',
            'mapping_source',
            'updated_at',
        ]
    )
    return result


def mapping_health(template) -> dict[str, Any]:
    """Diagnostics for admin UI / readiness checks."""
    schema = getattr(template, 'variable_schema', None) or []
    detected = list(getattr(template, 'msg91_detected_vars', None) or [])
    vmap = getattr(template, 'variable_map', None) or {}
    required = required_schema_names(schema)
    unmapped = [n for n in required if not (vmap.get(n) or '').strip()]
    targets = [str(v).strip() for v in vmap.values() if str(v).strip()]
    orphan_targets = [t for t in targets if detected and t not in detected]
    return {
        'synced': bool(getattr(template, 'msg91_synced_at', None)),
        'mapping_source': getattr(template, 'mapping_source', '') or '',
        'detected_vars': detected,
        'unmapped_required': unmapped,
        'orphan_targets': orphan_targets,
        'is_healthy': bool(detected) and not unmapped and not orphan_targets,
    }
