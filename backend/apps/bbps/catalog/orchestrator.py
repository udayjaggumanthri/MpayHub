"""
Single synchronous entrypoint for MDM catalog refresh + orchestration metadata.
"""

from __future__ import annotations

from typing import Iterable

from django.db import transaction
from django.conf import settings

from apps.bbps.catalog.env import active_bbps_environment
from apps.bbps.catalog.mdm_parse import iter_billers_from_payload, mdm_field_str, upstream_response_code
from apps.bbps.catalog.persist_biller import mark_unseen_billers_stale, persist_biller_from_mdm_row
from apps.integrations.billavenue.client import BillAvenueClient
from apps.integrations.billavenue.errors import BillAvenueAuthError, BillAvenueClientError
from apps.integrations.billavenue.registry import (
    get_billavenue_config_for_mode,
    normalize_billavenue_mode,
)
from apps.integrations.models import BillAvenueAgentProfile, BillAvenueConfig

# BillAvenue MDM rejects oversized multi-id requests (DE202 / empty gateway bodies).
# Keep chunks small; one admin sync still counts as one daily quota unit.
MDM_UPSTREAM_CHUNK_SIZE = 25


def _chunks(items: list[str], size: int) -> list[list[str]]:
    n = max(1, int(size or 1))
    return [items[i : i + n] for i in range(0, len(items), n)]


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

    Admin sync may target UAT or PROD independently of the partner live env:
    credentials and catalog writes are scoped to ``environment``.
    """

    @classmethod
    @transaction.atomic
    def sync_mdm_catalog(
        cls,
        biller_ids: Iterable[str] | None = None,
        *,
        request_id: str = '',
        environment: str | None = None,
    ) -> dict:
        biller_ids = [b for b in (biller_ids or []) if b]
        env = normalize_billavenue_mode(environment or active_bbps_environment())
        cfg = get_billavenue_config_for_mode(env, require_enabled=False)
        if not cfg or not str(getattr(cfg, 'base_url', '') or '').strip():
            raise BillAvenueClientError(
                f'BillAvenue {env.upper()} configuration missing. Save Base URL and credentials for {env.upper()} first.'
            )
        if not bool(getattr(cfg, 'enabled', False)):
            raise BillAvenueClientError(
                f'BillAvenue {env.upper()} is disabled. Enable it in BillAvenue Settings, then sync again.'
            )
        try:
            ba_client = BillAvenueClient(cfg)
        except BillAvenueClientError:
            raise
        except Exception as exc:
            raise BillAvenueClientError(f'Unable to start BillAvenue {env.upper()} client: {exc}') from exc

        agent_id = _default_agent_id_for_config(cfg)
        retry_without_agent_used = False
        sync_warning = ''
        normalized: dict = {}
        billers: list = []

        id_batches: list[list[str]]
        if biller_ids:
            id_batches = _chunks(biller_ids, MDM_UPSTREAM_CHUNK_SIZE)
        else:
            # Full-catalog pull (no ids) — single upstream call.
            id_batches = [[]]

        last_exc: Exception | None = None
        for batch_ids in id_batches:
            payload: dict = {}
            if agent_id:
                payload['agentId'] = agent_id
            if batch_ids:
                payload['billerId'] = batch_ids[0] if len(batch_ids) == 1 else batch_ids
            try:
                chunk_norm = ba_client.biller_info(payload).normalized
            except BillAvenueClientError as exc:
                msg = str(exc or '')
                msg_low = msg.lower()
                should_retry_without_agent = payload.get('agentId') and (
                    'code=205' in msg
                    or 'access denied' in msg_low
                    or 'unauthorized access' in msg_low
                    or isinstance(exc, BillAvenueAuthError)
                )
                if should_retry_without_agent:
                    payload_retry = dict(payload)
                    payload_retry.pop('agentId', None)
                    retry_without_agent_used = True
                    try:
                        chunk_norm = ba_client.biller_info(payload_retry).normalized
                    except BillAvenueClientError as exc2:
                        last_exc = exc2
                        # Soft-fail one chunk only when other chunks already returned rows.
                        if billers:
                            sync_warning = (
                                (sync_warning + ' ' if sync_warning else '')
                                + f'One MDM chunk failed ({exc2}); kept {len(billers)} biller(s) from earlier chunks.'
                            ).strip()
                            continue
                        raise
                else:
                    last_exc = exc
                    if billers:
                        sync_warning = (
                            (sync_warning + ' ' if sync_warning else '')
                            + f'One MDM chunk failed ({exc}); kept {len(billers)} biller(s) from earlier chunks.'
                        ).strip()
                        continue
                    raise

            if isinstance(chunk_norm, dict):
                normalized = chunk_norm
                chunk_rows = iter_billers_from_payload(chunk_norm)
                if isinstance(chunk_rows, list):
                    billers.extend(chunk_rows)

        if not billers and last_exc and not isinstance(normalized, dict):
            raise last_exc

        upstream_status_code = upstream_response_code(normalized if isinstance(normalized, dict) else None)
        if upstream_status_code == '205':
            sync_warning = (sync_warning + ' ' if sync_warning else '') + (
                'BillAvenue returned code 205 (entitlement/profile mismatch).'
            )
        if upstream_status_code == '202':
            sync_warning = (sync_warning + ' ' if sync_warning else '') + (
                'BillAvenue returned code 202 (request rejected — often too many IDs). Retry with fewer IDs.'
            )

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
            _, gc = persist_biller_from_mdm_row(raw, request_id=request_id, environment=env)
            updated += 1
            governance_created['categories'] += gc['categories']
            governance_created['providers'] += gc['providers']
            governance_created['maps'] += gc['maps']

        mark_unseen_billers_stale(biller_ids, seen, environment=env)

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
            # Auto plan-pull is expensive and currently flaky (PP002); only attempt on small syncs.
            cap = int(getattr(settings, 'BBPS_AUTO_PULL_PLANS_MAX_BILLERS', 50) or 50)
            cap = max(1, cap)
            eligible_ids = plan_pull_recommended[:cap]
            small_sync = len(biller_ids) <= 5
            if eligible_ids and small_sync:
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
            elif eligible_ids:
                auto_plan_pull['eligible_ids'] = eligible_ids
                auto_plan_pull['error'] = (
                    'Skipped auto plan-pull for large sync; use Admin → Pull plans for plan-enabled billers.'
                )

        out: dict = {
            'updated_count': updated,
            'biller_count': len(billers),
            'environment': env,
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
