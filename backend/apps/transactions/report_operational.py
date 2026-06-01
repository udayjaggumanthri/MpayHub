"""Platform-wide operational report querysets (Admin scope=platform)."""
from __future__ import annotations

from django.db.models import QuerySet

from apps.bbps.models import BillPayment
from apps.fund_management.models import LoadMoney, Payout
from apps.transactions.report_filters import apply_operational_report_filters


def platform_payin_queryset(request) -> QuerySet:
    qs = (
        LoadMoney.objects.filter(is_deleted=False)
        .select_related('user', 'package', 'package__payment_gateway', 'payment_gateway')
        .order_by('-created_at')
    )
    return apply_operational_report_filters(
        qs, request, id_field='transaction_id', include_customer_mobile=True
    )


def platform_payout_queryset(request) -> QuerySet:
    qs = (
        Payout.objects.filter(is_deleted=False)
        .select_related('user', 'bank_account')
        .order_by('-created_at')
    )
    return apply_operational_report_filters(qs, request, id_field='transaction_id')


def platform_bbps_queryset(request) -> QuerySet:
    qs = BillPayment.objects.filter(is_deleted=False).select_related('user').order_by('-created_at')
    return apply_operational_report_filters(qs, request, id_field='service_id')
