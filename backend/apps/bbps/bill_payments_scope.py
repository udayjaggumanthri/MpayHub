"""Bill payment list/detail scope — aligned with enterprise report scopes."""
from __future__ import annotations

from django.db.models import QuerySet
from rest_framework.exceptions import PermissionDenied

from apps.bbps.models import BillPayment
from apps.transactions.reporting_scope import get_report_scope, transaction_user_q


def bill_payments_base_queryset() -> QuerySet:
    return BillPayment.objects.filter(is_deleted=False).prefetch_related('attempts').select_related('user')


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
