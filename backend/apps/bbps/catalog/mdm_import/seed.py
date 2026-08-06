"""Seed BbpsBillerMaster rows from Excel metadata before MDM sync."""

from __future__ import annotations

from django.utils import timezone

from apps.bbps.models import BbpsBillerMaster
from apps.integrations.billavenue.registry import normalize_billavenue_mode


def seed_masters_from_excel_rows(*, environment: str, rows: list[dict]) -> dict[str, int]:
    env = normalize_billavenue_mode(environment)
    created = 0
    updated = 0
    now = timezone.now()
    for row in rows:
        bid = str(row.get('biller_id') or '').strip()
        if not bid:
            continue
        name = str(row.get('biller_name') or '').strip()
        category = str(row.get('biller_category') or '').strip()
        coverage = str(row.get('biller_coverage') or '').strip()[:80]

        obj = (
            BbpsBillerMaster.objects.filter(environment=env, biller_id=bid)
            .order_by('is_deleted', '-updated_at')
            .first()
        )
        if obj is None:
            BbpsBillerMaster.objects.create(
                environment=env,
                biller_id=bid,
                biller_name=name,
                biller_category=category,
                biller_coverage=coverage,
                biller_status='ACTIVE',
                is_active_local=True,
                source_type='excel_import',
                updated_by_admin_at=now,
            )
            created += 1
            continue

        obj.biller_name = name or obj.biller_name
        obj.biller_category = category or obj.biller_category
        obj.biller_coverage = coverage or obj.biller_coverage
        obj.biller_status = obj.biller_status or 'ACTIVE'
        obj.is_active_local = True
        obj.soft_deleted_at = None
        obj.is_deleted = False
        obj.deleted_at = None
        if obj.source_type != 'synced':
            obj.source_type = 'excel_import'
        obj.updated_by_admin_at = now
        obj.save()
        updated += 1
    return {'created': created, 'updated': updated}
