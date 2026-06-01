"""Query filters for BBPS bill payment list / export."""
from __future__ import annotations

from django.db.models import Q, QuerySet
from django.utils.dateparse import parse_date


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
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    return qs
