"""
Shared MDM sync batch runner: one BillAvenue call, shared daily quota.

Used by admin sync-billers HTTP and Excel MDM import queue.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.bbps.catalog.env import active_bbps_environment, biller_master_qs_for_env, catalog_counts_by_environment
from apps.bbps.models import BbpsSyncUsageLog
from apps.bbps.service_flow.biller_sync import sync_biller_info
from apps.integrations.billavenue.errors import BillAvenueAuthError, BillAvenueClientError, BillAvenueEntitlementError
from apps.integrations.billavenue.registry import (
    get_active_billavenue_config,
    get_billavenue_config_for_mode,
    normalize_billavenue_mode,
)

logger = logging.getLogger(__name__)

MDM_BATCH_MAX_IDS = 2000


class MdmSyncQuotaExhausted(Exception):
    def __init__(self, message: str, *, quota: dict | None = None):
        super().__init__(message)
        self.quota = quota or {}


class MdmSyncBatchError(Exception):
    def __init__(self, message: str, *, code: str = '', data: dict | None = None):
        super().__init__(message)
        self.code = code
        self.data = data or {}


def sync_quota_snapshot(environment: str | None = None) -> dict[str, Any]:
    live_mode = active_bbps_environment()
    env = normalize_billavenue_mode(environment or live_mode)
    cfg = get_billavenue_config_for_mode(env) or get_active_billavenue_config()
    max_calls = int(getattr(cfg, 'mdm_max_calls_per_day', 15) or 15) if cfg else 15
    today = timezone.localdate()
    row = BbpsSyncUsageLog.objects.filter(is_deleted=False, usage_date=today, environment=env).first()
    used = int(getattr(row, 'call_count', 0) or 0)
    visible = biller_master_qs_for_env(env).filter(soft_deleted_at__isnull=True).count()
    last_synced = (
        biller_master_qs_for_env(env)
        .exclude(last_synced_at__isnull=True)
        .order_by('-last_synced_at')
        .values_list('last_synced_at', flat=True)
        .first()
    )
    return {
        'usage_date': today,
        'environment': env,
        'live_mode': live_mode,
        'max_calls_per_day': max_calls,
        'used_calls_today': used,
        'remaining_calls_today': max(0, max_calls - used),
        'last_sync_at': row.updated_at if row else last_synced,
        'last_sync_result': str(getattr(row, 'last_status', '') or ''),
        'catalog_biller_count': visible,
        'catalog_counts': catalog_counts_by_environment(),
    }


def run_mdm_sync_batch(
    biller_ids: list[str] | None,
    *,
    environment: str,
    user=None,
    invalidate_cache=None,
) -> dict[str, Any]:
    """
    Consume one MDM quota call and sync up to 2000 biller IDs for ``environment``.

    Raises:
        MdmSyncQuotaExhausted: no remaining calls today
        MdmSyncBatchError: soft provider failure codes (001/205/PARSE)
        BillAvenueEntitlementError / BillAvenueClientError: hard provider failures
    """
    sync_env = normalize_billavenue_mode(environment)
    ids = [str(x or '').strip() for x in (biller_ids or []) if str(x or '').strip()]
    ids = list(dict.fromkeys(ids))
    if len(ids) > MDM_BATCH_MAX_IDS:
        raise MdmSyncBatchError(
            f'Maximum {MDM_BATCH_MAX_IDS} biller IDs per sync call',
            code='BATCH_TOO_LARGE',
        )

    quota = sync_quota_snapshot(sync_env)
    if quota['remaining_calls_today'] <= 0:
        raise MdmSyncQuotaExhausted(
            f'Daily BBPS sync quota exhausted for {sync_env.upper()}',
            quota=quota,
        )

    request_id = f"SYNC{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"
    usage_date = quota['usage_date']
    max_calls = int(quota['max_calls_per_day'] or 15)

    with transaction.atomic():
        usage, _ = BbpsSyncUsageLog.objects.select_for_update().get_or_create(
            usage_date=usage_date,
            environment=sync_env,
            is_deleted=False,
            defaults={
                'call_count': 0,
                'requested_ids_count': 0,
                'requested_by': user if user and getattr(user, 'is_authenticated', False) else None,
                'request_id': request_id,
            },
        )
        if usage.call_count >= max_calls:
            raise MdmSyncQuotaExhausted(
                f'Daily BBPS sync quota exhausted for {sync_env.upper()}',
                quota=sync_quota_snapshot(sync_env),
            )
        usage.call_count = F('call_count') + 1
        usage.requested_ids_count = F('requested_ids_count') + len(ids)
        usage.requested_by = user if user and getattr(user, 'is_authenticated', False) else None
        usage.request_id = request_id
        usage.last_status = 'started'
        usage.last_error = ''
        usage.meta = {'requested_ids': len(ids), 'environment': sync_env}
        usage.save(
            update_fields=[
                'call_count',
                'requested_ids_count',
                'requested_by',
                'request_id',
                'last_status',
                'last_error',
                'meta',
                'updated_at',
            ]
        )

    try:
        out = sync_biller_info(ids, request_id=request_id, environment=sync_env)
        BbpsSyncUsageLog.objects.filter(is_deleted=False, usage_date=usage_date, environment=sync_env).update(
            last_status='success',
            meta={'requested_ids': len(ids), 'synced': out.get('updated_count', 0), 'environment': sync_env},
        )
        if callable(invalidate_cache):
            invalidate_cache()
        from apps.bbps.service_flow.catalog_visibility import apply_cash_only_visibility_for_env
        from apps.bbps.service_flow.catalog_ux_settings import is_cash_only_for_users

        if is_cash_only_for_users(sync_env):
            out['visibility_apply'] = apply_cash_only_visibility_for_env(sync_env)
        out = dict(out or {})
        out['quota'] = sync_quota_snapshot(sync_env)
        out['request_id'] = request_id
        out['biller_ids'] = ids
        return out
    except BillAvenueEntitlementError as exc:
        BbpsSyncUsageLog.objects.filter(is_deleted=False, usage_date=usage_date, environment=sync_env).update(
            last_status='failed',
            last_error=str(exc),
        )
        # Soft-fail like other MDM gateway codes so admin UI keeps cached catalog usable.
        msg = str(exc or '')
        cached_count = biller_master_qs_for_env(sync_env).count()
        raise MdmSyncBatchError(
            msg,
            code='205',
            data={
                'billavenue_code': '205',
                'mdm_cached_count': cached_count,
                'quota': sync_quota_snapshot(sync_env),
                'request_id': request_id,
                'environment': sync_env,
            },
        ) from exc
    except BillAvenueAuthError as exc:
        BbpsSyncUsageLog.objects.filter(is_deleted=False, usage_date=usage_date, environment=sync_env).update(
            last_status='failed',
            last_error=str(exc),
        )
        msg = str(exc or '')
        cached_count = biller_master_qs_for_env(sync_env).count()
        raise MdmSyncBatchError(
            msg,
            code='AUTH',
            data={
                'billavenue_code': 'PP001',
                'mdm_cached_count': cached_count,
                'quota': sync_quota_snapshot(sync_env),
                'request_id': request_id,
                'biller_ids': ids,
                'environment': sync_env,
            },
        ) from exc
    except BillAvenueClientError as exc:
        BbpsSyncUsageLog.objects.filter(is_deleted=False, usage_date=usage_date, environment=sync_env).update(
            last_status='failed',
            last_error=str(exc),
        )
        msg = str(exc or '')
        code = ''
        low = msg.lower()
        if 'code=001' in msg:
            code = '001'
        elif 'code=205' in msg or 'de001' in low or 'invalid enc request' in low:
            code = '205'
        elif 'code=202' in msg or 'de202' in low:
            code = '202'
        elif 'missing responsecode' in low or 'missing responsecode' in msg:
            code = 'PARSE'
        elif 'access denied' in low or 'unauthorized access' in low:
            code = 'AUTH'
        if code:
            cached_count = biller_master_qs_for_env(sync_env).count()
            raise MdmSyncBatchError(
                msg,
                code=code,
                data={
                    'billavenue_code': code,
                    'mdm_cached_count': cached_count,
                    'quota': sync_quota_snapshot(sync_env),
                    'request_id': request_id,
                    'biller_ids': ids,
                    'environment': sync_env,
                },
            ) from exc
        raise
