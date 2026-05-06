"""
Single synchronous entrypoint for MDM catalog refresh + orchestration metadata.
"""

from __future__ import annotations

from typing import Iterable

from django.db import transaction
from django.conf import settings

from apps.bbps.catalog.mdm_parse import iter_billers_from_payload, mdm_field_str, upstream_response_code
from apps.bbps.catalog.persist_biller import mark_unseen_billers_stale, persist_biller_from_mdm_row
from apps.integrations.bbps_client import BBPSClient
from apps.integrations.billavenue.errors import BillAvenueClientError
from apps.integrations.models import BillAvenueAgentProfile, BillAvenueConfig


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


def _plan_pull_recommended_ids(synced_rows: list[dict]) -> list[str]:
    """Recommend explicit admin plan-pull when MDM signals plan involvement."""
    out: list[str] = []
    for raw in synced_rows:
        if not isinstance(raw, dict):
            continue
        bid = mdm_field_str(raw, 'billerId').strip()
        if not bid:
            continue
        plan_req = mdm_field_str(raw, 'planMdmRequirement').strip().upper()
        if not plan_req:
            continue
        if 'MANDATORY' in plan_req or 'OPTIONAL' in plan_req or plan_req in ('Y', 'YES', 'TRUE', '1'):
            if bid not in out:
                out.append(bid)
    return out


class CatalogOrchestrator:
    """
    Orchestrates BillAvenue MDM fetch → parse → persist catalog projections.

    All DB writes run inside ``transaction.atomic`` for parity with legacy sync.
    """

    @classmethod
    @transaction.atomic
    def sync_mdm_catalog(cls, biller_ids: Iterable[str] | None = None, *, request_id: str = '') -> dict:
        biller_ids = [b for b in (biller_ids or []) if b]
        client = BBPSClient()
        cfg = getattr(client, 'config', None) or _config_for_sync_client()
        agent_id = _default_agent_id_for_config(cfg)
        payload: dict = {}
        retry_without_agent_used = False
        sync_warning = ''
        if agent_id:
            payload['agentId'] = agent_id
        if biller_ids:
            payload['billerId'] = biller_ids[0] if len(biller_ids) == 1 else biller_ids
        try:
            normalized = client.biller_info(payload)
        except BillAvenueClientError as exc:
            msg = str(exc or '')
            if 'code=205' in msg and payload.get('agentId'):
                payload_retry = dict(payload)
                payload_retry.pop('agentId', None)
                retry_without_agent_used = True
                normalized = client.biller_info(payload_retry)
            else:
                raise

        upstream_status_code = upstream_response_code(normalized if isinstance(normalized, dict) else None)
        if upstream_status_code == '205':
            sync_warning = 'BillAvenue returned code 205 (entitlement/profile mismatch).'

        billers = iter_billers_from_payload(normalized) if isinstance(normalized, dict) else []

        seen: set[str] = set()
        updated = 0
        governance_created = {'categories': 0, 'providers': 0, 'maps': 0}

        for raw in billers:
            if not isinstance(raw, dict):
                continue
            bid = mdm_field_str(raw, 'billerId').strip()
            if not bid:
                continue
            seen.add(bid)
            _, gc = persist_biller_from_mdm_row(raw, request_id=request_id)
            updated += 1
            governance_created['categories'] += gc['categories']
            governance_created['providers'] += gc['providers']
            governance_created['maps'] += gc['maps']

        mark_unseen_billers_stale(biller_ids, seen)

        sample_categories = sorted(
            list(
                {
                    str(mdm_field_str(x, 'billerCategory') or '').strip()
                    for x in billers
                    if isinstance(x, dict) and str(mdm_field_str(x, 'billerCategory') or '').strip()
                }
            )
        )[:20]

        plan_pull_recommended = _plan_pull_recommended_ids([x for x in billers if isinstance(x, dict)])
        auto_plan_pull = {
            'attempted': False,
            'eligible_ids': [],
            'processed_ids': [],
            'plan_count': 0,
            'error': '',
        }
        if bool(getattr(settings, 'BBPS_AUTO_PULL_PLANS_ON_SYNC', True)):
            cap = int(getattr(settings, 'BBPS_AUTO_PULL_PLANS_MAX_BILLERS', 50) or 50)
            cap = max(1, cap)
            eligible_ids = plan_pull_recommended[:cap]
            if eligible_ids:
                auto_plan_pull['attempted'] = True
                auto_plan_pull['eligible_ids'] = eligible_ids
                try:
                    # Local import keeps catalog orchestration loosely coupled from plan module internals.
                    from apps.bbps.service_flow.plan_service import pull_biller_plans
                    plan_out = pull_biller_plans(biller_ids=eligible_ids)
                    auto_plan_pull['processed_ids'] = eligible_ids
                    auto_plan_pull['plan_count'] = int(plan_out.get('plan_count') or 0)
                except Exception as exc:
                    auto_plan_pull['error'] = str(exc or '')

        out: dict = {
            'updated_count': updated,
            'biller_count': len(billers),
            'agent_id_used': agent_id or None,
            'retry_without_agent_used': retry_without_agent_used,
            'upstream_status_code': upstream_status_code,
            'sample_categories': sample_categories,
            'mapping_ready': bool(len(billers) > 0),
            'governance_created': governance_created,
            'plan_pull_recommended': plan_pull_recommended,
            'auto_plan_pull': auto_plan_pull,
        }
        if sync_warning:
            out['warning'] = sync_warning
        if not billers and isinstance(normalized, dict):
            out['mdm_root_keys'] = sorted([str(k) for k in normalized.keys()])[:40]
            out['normalized_preview'] = {k: type(v).__name__ for k, v in list(normalized.items())[:10]}
        return out
