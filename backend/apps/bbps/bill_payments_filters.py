"""Query filters for BBPS bill payment list / export."""
from __future__ import annotations

from django.db.models import Q, QuerySet
from django.utils.dateparse import parse_date

from apps.transactions.report_filters import created_at_range_kwargs


def apply_bill_payments_list_filters(qs: QuerySet, request) -> QuerySet:
    status = (request.query_params.get('status') or '').strip().upper()
    if status and status not in ('ALL', 'ANY'):
        if status == 'FAILURE':
            status = 'FAILED'
        qs = qs.filter(status=status)

    search = (request.query_params.get('search') or request.query_params.get('service_id') or '').strip()
    if search:
        qs = qs.filter(
            Q(service_id__icontains=search)
            | Q(request_id__icontains=search)
            | Q(biller__icontains=search)
            | Q(biller_id__icontains=search)
        )

    date_from = parse_date((request.query_params.get('date_from') or '').strip())
    date_to = parse_date((request.query_params.get('date_to') or '').strip())
    kwargs = created_at_range_kwargs(date_from, date_to)
    if kwargs:
        qs = qs.filter(**kwargs)

    return qs
