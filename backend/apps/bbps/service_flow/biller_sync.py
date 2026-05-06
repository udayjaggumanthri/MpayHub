"""
Legacy entrypoint for MDM biller sync.

Parsing lives in ``apps.bbps.catalog.mdm_parse``; persistence in ``catalog.persist_biller``;
orchestration in ``catalog.orchestrator``.
"""

from __future__ import annotations

from typing import Iterable

from apps.bbps.catalog.mdm_parse import iter_billers_from_payload
from apps.bbps.catalog.orchestrator import CatalogOrchestrator
from apps.bbps.catalog.persist_biller import upsert_governance_rows as _upsert_governance_rows


def _iter_billers(payload, _depth: int = 0):
    """Backward-compatible alias for tests (same as ``iter_billers_from_payload``)."""
    return iter_billers_from_payload(payload, _depth)


def sync_biller_info(
    biller_ids: Iterable[str] | None = None,
    *,
    request_id: str = '',
) -> dict:
    """Fetch BillAvenue MDM and refresh biller cache tables."""
    return CatalogOrchestrator.sync_mdm_catalog(biller_ids, request_id=request_id)


__all__ = ['sync_biller_info', '_iter_billers', '_upsert_governance_rows']
