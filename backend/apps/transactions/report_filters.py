"""Unified query filters for enterprise reports."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db.models import Q, QuerySet
from django.utils.dateparse import parse_date

from apps.authentication.models import User
from apps.fund_management.models import LoadMoney


def _norm_mobile(raw: str | None) -> str:
    s = (raw or '').strip()
    if not s:
        return ''
    digits = ''.join(c for c in s if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def apply_date_filters(qs: QuerySet, request, field_prefix: str = '') -> QuerySet:
    prefix = f'{field_prefix}__' if field_prefix else ''
    date_from = parse_date((request.query_params.get('date_from') or '').strip())
    date_to = parse_date((request.query_params.get('date_to') or '').strip())
    if date_from:
        qs = qs.filter(**{f'{prefix}created_at__date__gte': date_from})
    if date_to:
        qs = qs.filter(**{f'{prefix}created_at__date__lte': date_to})
    return qs


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
