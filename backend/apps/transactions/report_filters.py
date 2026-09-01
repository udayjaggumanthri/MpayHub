"""Unified query filters for enterprise reports."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.authentication.models import User
from apps.fund_management.models import LoadMoney


def _norm_mobile(raw: str | None) -> str:
    s = (raw or '').strip()
    if not s:
        return ''
    digits = ''.join(c for c in s if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def start_of_local_day(day):
    naive = datetime.combine(day, time.min)
    if timezone.is_naive(timezone.now()):
        return naive
    return timezone.make_aware(naive, timezone.get_current_timezone())


def created_at_range_kwargs(date_from, date_to, field_prefix: str = '') -> dict:
    """Timestamp range so `created_at` indexes can be used (not `created_at::date`)."""
    prefix = f'{field_prefix}__' if field_prefix else ''
    kwargs = {}
    if date_from:
        kwargs[f'{prefix}created_at__gte'] = start_of_local_day(date_from)
    if date_to:
        kwargs[f'{prefix}created_at__lt'] = start_of_local_day(date_to + timedelta(days=1))
    return kwargs


def apply_date_filters(qs: QuerySet, request, field_prefix: str = '') -> QuerySet:
    date_from = parse_date((request.query_params.get('date_from') or '').strip())
    date_to = parse_date((request.query_params.get('date_to') or '').strip())
    kwargs = created_at_range_kwargs(date_from, date_to, field_prefix)
    return qs.filter(**kwargs) if kwargs else qs


def apply_transaction_report_filters(qs: QuerySet, request, *, include_customer_mobile: bool = False) -> QuerySet:
    qs = apply_date_filters(qs, request)

    status = (request.query_params.get('status') or '').strip().upper()
    if status and status not in ('ALL', 'ANY'):
        if status == 'FAILURE':
            status = 'FAILED'
        qs = qs.filter(status=status)

    service_id = (request.query_params.get('service_id') or '').strip()
    if service_id:
        qs = qs.filter(service_id__icontains=service_id)

    mobile = _norm_mobile(request.query_params.get('mobile'))
    if mobile:
        user_phone = Q(user__phone=mobile)
        if include_customer_mobile:
            lm_ids = LoadMoney.objects.filter(customer_phone=mobile).values_list('transaction_id', flat=True)
            qs = qs.filter(user_phone | Q(service_id__in=lm_ids))
        else:
            qs = qs.filter(user_phone)

    amount_min = (request.query_params.get('amount_min') or '').strip()
    amount_max = (request.query_params.get('amount_max') or '').strip()
    try:
        if amount_min:
            qs = qs.filter(amount__gte=Decimal(amount_min))
    except (InvalidOperation, ValueError):
        pass
    try:
        if amount_max:
            qs = qs.filter(amount__lte=Decimal(amount_max))
    except (InvalidOperation, ValueError):
        pass

    service_type = (request.query_params.get('service_type') or '').strip().lower()
    if service_type and service_type != 'all':
        qs = qs.filter(service_family=service_type)

    agent_role = (request.query_params.get('agent_role') or '').strip()
    if agent_role:
        qs = qs.filter(user__role__iexact=agent_role)

    return qs


def apply_operational_report_filters(
    qs: QuerySet,
    request,
    *,
    id_field: str = 'transaction_id',
    include_customer_mobile: bool = False,
) -> QuerySet:
    """Filters for LoadMoney / Payout / BillPayment platform reports."""
    qs = apply_date_filters(qs, request)

    status = (request.query_params.get('status') or '').strip().upper()
    if status and status not in ('ALL', 'ANY'):
        if status == 'FAILURE':
            status = 'FAILED'
        qs = qs.filter(status=status)

    service_id = (request.query_params.get('service_id') or '').strip()
    if service_id:
        qs = qs.filter(**{f'{id_field}__icontains': service_id})

    mobile = _norm_mobile(request.query_params.get('mobile'))
    if mobile:
        user_phone = Q(user__phone=mobile)
        if include_customer_mobile and id_field == 'transaction_id':
            qs = qs.filter(user_phone | Q(customer_phone=mobile))
        else:
            qs = qs.filter(user_phone)

    amount_min = (request.query_params.get('amount_min') or '').strip()
    amount_max = (request.query_params.get('amount_max') or '').strip()
    try:
        if amount_min:
            qs = qs.filter(amount__gte=Decimal(amount_min))
    except (InvalidOperation, ValueError):
        pass
    try:
        if amount_max:
            qs = qs.filter(amount__lte=Decimal(amount_max))
    except (InvalidOperation, ValueError):
        pass

    agent_role = (request.query_params.get('agent_role') or '').strip()
    if agent_role:
        qs = qs.filter(user__role__iexact=agent_role)

    collection_rail = (request.query_params.get('collection_rail') or request.query_params.get('rail') or '').strip().lower()
    if collection_rail and collection_rail not in ('all', 'any'):
        qs = qs.filter(collection_rail=collection_rail)

    utr = (request.query_params.get('utr') or '').strip()
    if utr:
        qs = qs.filter(utr__icontains=utr)

    return qs


def apply_passbook_report_filters(qs: QuerySet, request) -> QuerySet:
    qs = apply_date_filters(qs, request)

    mobile = _norm_mobile(request.query_params.get('mobile'))
    if mobile:
        qs = qs.filter(user__phone=mobile)

    search = (request.query_params.get('search') or '').strip()
    if search:
        qs = qs.filter(Q(service_id__icontains=search) | Q(description__icontains=search))

    wallet_type = (request.query_params.get('wallet_type') or '').strip()
    if wallet_type in ('main', 'commission', 'bbps', 'profit'):
        qs = qs.filter(wallet_type=wallet_type)

    amount_min = (request.query_params.get('amount_min') or '').strip()
    amount_max = (request.query_params.get('amount_max') or '').strip()
    try:
        if amount_min:
            qs = qs.filter(Q(debit_amount__gte=Decimal(amount_min)) | Q(credit_amount__gte=Decimal(amount_min)))
    except (InvalidOperation, ValueError):
        pass
    try:
        if amount_max:
            qs = qs.filter(Q(debit_amount__lte=Decimal(amount_max)) | Q(credit_amount__lte=Decimal(amount_max)))
    except (InvalidOperation, ValueError):
        pass

    return qs


def apply_commission_ledger_filters(qs: QuerySet, request) -> QuerySet:
    qs = apply_date_filters(qs, request)
    ref = (request.query_params.get('service_id') or '').strip()
    if ref:
        qs = qs.filter(reference_service_id__icontains=ref)

    mobile = _norm_mobile(request.query_params.get('mobile'))
    if mobile:
        src_ids = list(User.objects.filter(phone=mobile).values_list('pk', flat=True))
        q = Q(user__phone=mobile)
        if src_ids:
            q |= Q(meta__source_user_id__in=src_ids)
        qs = qs.filter(q)

    agent_role = (request.query_params.get('agent_role') or '').strip()
    if agent_role:
        qs = qs.filter(Q(source_role__iexact=agent_role) | Q(meta__source_role__iexact=agent_role))

    amount_min = (request.query_params.get('amount_min') or '').strip()
    amount_max = (request.query_params.get('amount_max') or '').strip()
    try:
        if amount_min:
            qs = qs.filter(amount__gte=Decimal(amount_min))
    except (InvalidOperation, ValueError):
        pass
    try:
        if amount_max:
            qs = qs.filter(amount__lte=Decimal(amount_max))
    except (InvalidOperation, ValueError):
        pass

    return qs
