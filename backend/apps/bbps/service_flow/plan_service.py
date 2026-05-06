from __future__ import annotations

from django.utils import timezone

from apps.bbps.models import BbpsBillerMaster, BbpsBillerPlanMeta, BbpsPlanPullRun
from apps.integrations.bbps_client import BBPSClient
from apps.integrations.billavenue.parsers import _get_ci


def _iter_plan_rows(node):
    """Yield candidate plan rows from varied BillAvenue response shapes."""
    if isinstance(node, list):
        for item in node:
            yield from _iter_plan_rows(item)
        return
    if not isinstance(node, dict):
        return

    plan_id = str(_get_ci(node, 'planId') or '').strip()
    biller_id = str(_get_ci(node, 'billerId') or '').strip()
    amount = _get_ci(node, 'amountInRupees')
    category = _get_ci(node, 'categoryType')
    if plan_id or (biller_id and (amount is not None or category is not None)):
        yield node

    # recurse into nested dict/list values
    for v in node.values():
        if isinstance(v, (dict, list)):
            yield from _iter_plan_rows(v)


def _normalize_plan_id(row: dict, *, fallback_biller_id: str, ordinal: int) -> str:
    plan_id = str(_get_ci(row, 'planId') or '').strip()
    if plan_id:
        return plan_id
    # Some providers omit planId; generate a stable, data-based synthetic key.
    parts = [
        fallback_biller_id.strip(),
        str(_get_ci(row, 'categoryType') or '').strip(),
        str(_get_ci(row, 'categorySubType') or '').strip(),
        str(_get_ci(row, 'amountInRupees') or '').strip(),
        str(_get_ci(row, 'effectiveFrom') or '').strip(),
        str(_get_ci(row, 'effectiveTo') or '').strip(),
        str(_get_ci(row, 'planDesc') or '').strip(),
    ]
    return 'SYNTH-' + '-'.join(parts + [str(ordinal)])


def pull_biller_plans(*, biller_ids: list[str]) -> dict:
    client = BBPSClient()
    cleaned_ids = [str(x or '').strip() for x in (biller_ids or []) if str(x or '').strip()]
    payload = {'billerId': cleaned_ids} if cleaned_ids else {}
    resp = client.pull_plans(payload)

    details = list(_iter_plan_rows(resp))
    seen = set()
    deduped = []
    for d in details:
        key = (
            str(_get_ci(d, 'billerId') or '').strip(),
            str(_get_ci(d, 'planId') or '').strip(),
            str(_get_ci(d, 'categoryType') or '').strip(),
            str(_get_ci(d, 'amountInRupees') or '').strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(d)
    details = deduped

    count = 0
    root_biller_id = str(_get_ci(resp, 'billerId') or '').strip()
    fallback_biller_id = cleaned_ids[0] if len(cleaned_ids) == 1 else root_biller_id
    for idx, d in enumerate(details, start=1):
        bid = str(_get_ci(d, 'billerId') or '').strip() or fallback_biller_id
        if not bid:
            continue
        status = str(_get_ci(d, 'status') or '').upper()
        master = BbpsBillerMaster.objects.filter(biller_id=bid, is_deleted=False).first()
        if not master:
            continue
        plan_id = _normalize_plan_id(d, fallback_biller_id=bid, ordinal=idx)
        BbpsBillerPlanMeta.objects.update_or_create(
            biller=master,
            plan_id=plan_id,
            defaults={
                'category_type': str(_get_ci(d, 'categoryType') or ''),
                'category_sub_type': str(_get_ci(d, 'categorySubType') or ''),
                'amount_in_rupees': str(_get_ci(d, 'amountInRupees') or '0'),
                'plan_desc': str(_get_ci(d, 'planDesc') or ''),
                'plan_additional_info': _get_ci(d, 'planAddnlInfo') or {},
                'status': status or 'ACTIVE',
                'effective_from': _get_ci(d, 'effectiveFrom') or None,
                'effective_to': _get_ci(d, 'effectiveTo') or None,
            },
        )
        count += 1

    run = BbpsPlanPullRun.objects.create(
        response_code=str(resp.get('responseCode') or ''),
        requested_biller_ids=biller_ids,
        plan_count=count,
        response_payload=resp,
    )
    return {'run_id': run.pk, 'plan_count': count, 'response': resp}
