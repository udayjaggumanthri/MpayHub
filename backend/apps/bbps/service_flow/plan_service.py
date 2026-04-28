from __future__ import annotations

from django.utils import timezone

from apps.bbps.models import BbpsBillerMaster, BbpsBillerPlanMeta, BbpsPlanPullRun
from apps.integrations.bbps_client import BBPSClient


def pull_biller_plans(*, biller_ids: list[str]) -> dict:
    client = BBPSClient()
    payload = {'billerId': biller_ids or []}
    resp = client.pull_plans(payload)

    details = resp.get('planDetails') or resp.get('planDetailsResponse', {}).get('planDetails') or []
    if isinstance(details, dict):
        details = [details]

    count = 0
    today = timezone.localdate()
    for d in details:
        bid = str(d.get('billerId') or '')
        if not bid:
            continue
        status = str(d.get('status') or '').upper()
        # Compliance: keep only ACTIVE plans in runtime catalog.
        if status and status != 'ACTIVE':
            continue
        master = BbpsBillerMaster.objects.filter(biller_id=bid, is_deleted=False).first()
        if not master:
            continue
        effective_to = d.get('effectiveTo') or None
        if effective_to and str(effective_to) < str(today):
            continue
        BbpsBillerPlanMeta.objects.update_or_create(
            biller=master,
            plan_id=str(d.get('planId') or ''),
            defaults={
                'category_type': str(d.get('categoryType') or ''),
                'category_sub_type': str(d.get('categorySubType') or ''),
                'amount_in_rupees': str(d.get('amountInRupees') or '0'),
                'plan_desc': str(d.get('planDesc') or ''),
                'plan_additional_info': d.get('planAddnlInfo') or {},
                'status': status or 'ACTIVE',
                'effective_from': d.get('effectiveFrom') or None,
                'effective_to': d.get('effectiveTo') or None,
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
