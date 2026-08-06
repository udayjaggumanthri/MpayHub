"""Create and drain Excel MDM import jobs with shared quota batches."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.bbps.catalog.mdm_import.excel_parser import parse_mdm_excel
from apps.bbps.catalog.mdm_import.seed import seed_masters_from_excel_rows
from apps.bbps.models import BbpsMdmImportItem, BbpsMdmImportJob
from apps.bbps.service_flow.mdm_sync_batch import (
    MDM_BATCH_MAX_IDS,
    MdmSyncBatchError,
    MdmSyncQuotaExhausted,
    run_mdm_sync_batch,
    sync_quota_snapshot,
)
from apps.integrations.billavenue.errors import BillAvenueClientError, BillAvenueEntitlementError
from apps.integrations.billavenue.registry import normalize_billavenue_mode

logger = logging.getLogger(__name__)


def _refresh_job_counts(job: BbpsMdmImportJob) -> BbpsMdmImportJob:
    agg = (
        BbpsMdmImportItem.objects.filter(job=job, is_deleted=False)
        .values('status')
        .annotate(c=Count('id'))
    )
    counts = {r['status']: int(r['c'] or 0) for r in agg}
    job.total_ids = sum(counts.values())
    job.pending_ids = counts.get('pending', 0)
    job.synced_ids = counts.get('synced', 0)
    job.failed_ids = counts.get('failed', 0) + counts.get('skipped', 0)
    if job.pending_ids <= 0 and job.total_ids > 0 and not job.error_summary:
        job.status = 'completed'
        job.completed_at = timezone.now()
    elif job.pending_ids > 0 and (job.synced_ids > 0 or job.failed_ids > 0):
        job.status = 'partial'
    elif job.pending_ids > 0:
        job.status = 'queued' if job.status not in ('processing', 'partial') else job.status
    job.save(
        update_fields=[
            'total_ids',
            'pending_ids',
            'synced_ids',
            'failed_ids',
            'status',
            'completed_at',
            'updated_at',
        ]
    )
    return job


def create_job_from_upload(
    *,
    file_obj,
    filename: str,
    environment: str,
    user=None,
    auto_drain: bool = True,
    invalidate_cache=None,
) -> dict[str, Any]:
    env = normalize_billavenue_mode(environment)
    rows = parse_mdm_excel(file_obj, filename=filename)
    seed_stats = seed_masters_from_excel_rows(environment=env, rows=rows)

    with transaction.atomic():
        job = BbpsMdmImportJob.objects.create(
            environment=env,
            original_filename=str(filename or '')[:255],
            status='queued',
            total_ids=len(rows),
            pending_ids=len(rows),
            uploaded_by=user if user and getattr(user, 'is_authenticated', False) else None,
            started_at=timezone.now(),
        )
        BbpsMdmImportItem.objects.bulk_create(
            [
                BbpsMdmImportItem(
                    job=job,
                    biller_id=r['biller_id'],
                    biller_name=r.get('biller_name') or '',
                    biller_category=r.get('biller_category') or '',
                    biller_coverage=r.get('biller_coverage') or '',
                    status='pending',
                )
                for r in rows
            ],
            batch_size=1000,
        )

    drain_result = None
    if auto_drain:
        drain_result = drain_job(job.pk, user=user, invalidate_cache=invalidate_cache)
        job.refresh_from_db()
    else:
        job = _refresh_job_counts(job)

    return {
        'job': job,
        'seed': seed_stats,
        'drain': drain_result,
        'quota': sync_quota_snapshot(env),
    }


def destroy_job(job_id: int, *, reason: str = '') -> dict[str, Any]:
    """
    Stop an MDM import job and remove it from the admin queue.

    Soft-deletes the job + items, marks status cancelled, and skips remaining
    pending IDs so process_pending / Process remaining cannot revive it.
    """
    job = BbpsMdmImportJob.objects.filter(pk=job_id, is_deleted=False).first()
    if not job:
        raise ValueError('Import job not found')

    now = timezone.now()
    note = (reason or 'Destroyed by admin').strip()[:500]
    pending_skipped = BbpsMdmImportItem.objects.filter(
        job=job, is_deleted=False, status='pending'
    ).update(
        status='skipped',
        last_error=note[:2000],
        updated_at=now,
    )
    # Capture final counts while items are still visible, then hide them.
    job = _refresh_job_counts(job)
    final_synced = int(job.synced_ids or 0)
    final_failed = int(job.failed_ids or 0)
    final_total = int(job.total_ids or 0)

    BbpsMdmImportItem.objects.filter(job=job, is_deleted=False).update(
        is_deleted=True,
        deleted_at=now,
        updated_at=now,
    )
    job.status = 'cancelled'
    job.pending_ids = 0
    job.synced_ids = final_synced
    job.failed_ids = final_failed
    job.total_ids = final_total
    job.completed_at = now
    job.error_summary = note
    job.is_deleted = True
    job.deleted_at = now
    job.save(
        update_fields=[
            'status',
            'pending_ids',
            'synced_ids',
            'failed_ids',
            'total_ids',
            'completed_at',
            'error_summary',
            'is_deleted',
            'deleted_at',
            'updated_at',
        ]
    )
    logger.info(
        'mdm-import job=%s destroyed pending_skipped=%s reason=%s',
        job.pk,
        pending_skipped,
        note,
    )
    return {
        'job_id': job.pk,
        'status': job.status,
        'pending_skipped': pending_skipped,
        'synced_ids': final_synced,
        'failed_ids': final_failed,
        'total_ids': final_total,
        'destroyed': True,
    }


def drain_job(job_id: int, *, user=None, invalidate_cache=None, max_batches: int | None = None) -> dict[str, Any]:
    job = BbpsMdmImportJob.objects.filter(pk=job_id, is_deleted=False).first()
    if not job:
        raise ValueError('Import job not found')
    if job.status == 'cancelled':
        raise ValueError('Import job was cancelled and cannot be processed')

    env = normalize_billavenue_mode(job.environment)
    job.status = 'processing'
    if not job.started_at:
        job.started_at = timezone.now()
    job.save(update_fields=['status', 'started_at', 'updated_at'])

    batches_run = 0
    last_error = ''
    stopped_reason = ''

    while True:
        # Allow mid-drain cancel/destroy from another request.
        job.refresh_from_db()
        if job.is_deleted or job.status == 'cancelled':
            stopped_reason = 'cancelled'
            break

        quota = sync_quota_snapshot(env)
        if quota['remaining_calls_today'] <= 0:
            stopped_reason = 'quota_exhausted'
            break
        if max_batches is not None and batches_run >= max_batches:
            stopped_reason = 'max_batches'
            break

        pending_qs = BbpsMdmImportItem.objects.filter(job=job, is_deleted=False, status='pending').order_by('id')
        batch_ids = list(pending_qs.values_list('biller_id', flat=True)[:MDM_BATCH_MAX_IDS])
        if not batch_ids:
            stopped_reason = 'done'
            break

        try:
            out = run_mdm_sync_batch(
                batch_ids,
                environment=env,
                user=user,
                invalidate_cache=invalidate_cache,
            )
            now = timezone.now()
            BbpsMdmImportItem.objects.filter(
                job=job, is_deleted=False, biller_id__in=batch_ids, status='pending'
            ).update(status='synced', last_error='', last_synced_at=now, updated_at=now)
            batches_run += 1
            logger.info(
                'mdm-import job=%s env=%s batch=%s synced=%s',
                job.pk,
                env,
                batches_run,
                out.get('updated_count'),
            )
        except MdmSyncQuotaExhausted:
            stopped_reason = 'quota_exhausted'
            break
        except MdmSyncBatchError as exc:
            last_error = str(exc)
            now = timezone.now()
            # Soft provider codes: keep items pending for retry next day if cache usable,
            # but mark failed when batch is clearly bad.
            if exc.code in ('001', '205', 'PARSE'):
                BbpsMdmImportItem.objects.filter(
                    job=job, is_deleted=False, biller_id__in=batch_ids, status='pending'
                ).update(status='failed', last_error=last_error[:2000], updated_at=now)
            else:
                BbpsMdmImportItem.objects.filter(
                    job=job, is_deleted=False, biller_id__in=batch_ids, status='pending'
                ).update(status='failed', last_error=last_error[:2000], updated_at=now)
            batches_run += 1
            job.error_summary = last_error[:2000]
            job.save(update_fields=['error_summary', 'updated_at'])
            stopped_reason = f'batch_error:{exc.code or "error"}'
            # Continue if quota remains (next pending batch); for full-sheet failures stop.
            if not BbpsMdmImportItem.objects.filter(job=job, is_deleted=False, status='pending').exists():
                break
        except (BillAvenueEntitlementError, BillAvenueClientError) as exc:
            last_error = str(exc)
            now = timezone.now()
            BbpsMdmImportItem.objects.filter(
                job=job, is_deleted=False, biller_id__in=batch_ids, status='pending'
            ).update(status='failed', last_error=last_error[:2000], updated_at=now)
            batches_run += 1
            job.error_summary = last_error[:2000]
            job.status = 'partial'
            job.save(update_fields=['error_summary', 'status', 'updated_at'])
            stopped_reason = 'provider_error'
            break
        except Exception as exc:
            last_error = str(exc)
            logger.exception('mdm-import drain failed job=%s', job.pk)
            job.error_summary = last_error[:2000]
            job.status = 'failed'
            job.save(update_fields=['error_summary', 'status', 'updated_at'])
            stopped_reason = 'unexpected'
            break

    job = _refresh_job_counts(job)
    job.refresh_from_db()
    if job.is_deleted or job.status == 'cancelled' or stopped_reason == 'cancelled':
        # Destroy/cancel already finalized the row; do not overwrite.
        pass
    elif job.pending_ids > 0 and stopped_reason == 'quota_exhausted':
        job.status = 'partial'
        job.save(update_fields=['status', 'updated_at'])
    elif job.pending_ids <= 0 and job.failed_ids > 0 and job.synced_ids == 0:
        job.status = 'failed'
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'completed_at', 'updated_at'])
    elif job.pending_ids <= 0:
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'completed_at', 'updated_at'])

    return {
        'job_id': job.pk,
        'batches_run': batches_run,
        'stopped_reason': stopped_reason,
        'last_error': last_error,
        'quota': sync_quota_snapshot(env),
        'status': job.status,
        'pending_ids': job.pending_ids,
        'synced_ids': job.synced_ids,
        'failed_ids': job.failed_ids,
        'total_ids': job.total_ids,
    }


def process_pending_jobs(*, environment: str | None = None, max_jobs: int = 5, user=None, invalidate_cache=None) -> dict[str, Any]:
    qs = BbpsMdmImportJob.objects.filter(
        is_deleted=False,
        status__in=['queued', 'partial', 'processing'],
    ).filter(Q(pending_ids__gt=0) | Q(status='queued'))
    if environment in ('uat', 'prod'):
        qs = qs.filter(environment=environment)
    jobs = list(qs.order_by('created_at')[: max(1, max_jobs)])
    results = []
    for job in jobs:
        results.append(drain_job(job.pk, user=user, invalidate_cache=invalidate_cache))
    return {'processed': len(results), 'results': results}
