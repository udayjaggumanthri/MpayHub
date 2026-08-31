"""Platform-wide operational report querysets (Admin scope=platform)."""
from __future__ import annotations

from django.db.models import QuerySet

from apps.bbps.models import BillPayment
from apps.fund_management.models import LoadMoney, Payout
from apps.transactions.report_filters import apply_operational_report_filters
from apps.transactions.reporting_scope import (
    TEAM_SCOPE_ROLES,
    get_report_scope,
    team_transaction_user_ids,
)
from rest_framework.exceptions import PermissionDenied


def platform_payin_queryset(request) -> QuerySet:
    qs = (
        LoadMoney.objects.filter(is_deleted=False)
        .select_related(
            'user', 'package', 'package__payment_gateway', 'payment_gateway', 'pay_in_qr_account'
        )
        .order_by('-created_at')
    )
    return apply_operational_report_filters(
        qs, request, id_field='transaction_id', include_customer_mobile=True
    )


def user_scope_payin_load_money_queryset(request) -> QuerySet:
    """Pay-in report rows for self/team scope (includes QR pending review)."""
    scope = get_report_scope(request)
    qs = (
        LoadMoney.objects.filter(is_deleted=False)
        .select_related(
            'user', 'package', 'package__payment_gateway', 'payment_gateway', 'pay_in_qr_account'
        )
        .order_by('-created_at')
    )
    user = request.user
    if scope == 'self':
        qs = qs.filter(user=user)
    else:
        role = getattr(user, 'role', None)
        if role not in TEAM_SCOPE_ROLES:
            raise PermissionDenied('Team report scope is not enabled for your role.')
        if role == 'Admin':
            qs = qs.exclude(user=user)
        else:
            ids = team_transaction_user_ids(user)
            qs = qs.filter(user_id__in=ids) if ids else qs.none()
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
