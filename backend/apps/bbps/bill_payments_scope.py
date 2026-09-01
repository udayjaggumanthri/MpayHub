"""Bill payment list/detail scope — aligned with enterprise report scopes."""
from __future__ import annotations

from django.db.models import Prefetch, QuerySet
from rest_framework.exceptions import PermissionDenied

from apps.bbps.models import BillPayment, BbpsPaymentAttempt
from apps.transactions.reporting_scope import get_report_scope, transaction_user_q


def _attempts_prefetch() -> Prefetch:
    return Prefetch(
        'attempts',
        queryset=BbpsPaymentAttempt.objects.filter(is_deleted=False).order_by('-created_at'),
        to_attr='prefetched_attempts',
    )


def bill_payments_base_queryset() -> QuerySet:
    return (
        BillPayment.objects.filter(is_deleted=False)
        .select_related('user', 'user__profile')
        .prefetch_related(_attempts_prefetch())
    )


def bill_payments_queryset_for_request(request) -> QuerySet:
    """Filter BillPayment rows by scope=self|team|platform (platform = Admin only)."""
    scope = get_report_scope(request)
    qs = bill_payments_base_queryset().order_by('-created_at')
    if scope == 'platform':
        return qs
    try:
        uq = transaction_user_q(request)
    except PermissionDenied:
        raise
    return qs.filter(uq)


def bill_payment_detail_queryset_for_request(request) -> QuerySet:
    return bill_payments_queryset_for_request(request)


def can_access_bill_payment(request, payment: BillPayment) -> bool:
    return bill_payment_detail_queryset_for_request(request).filter(pk=payment.pk).exists()
