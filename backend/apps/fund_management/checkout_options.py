"""Unified pay-in checkout options: payment gateways + manual QR accounts."""
from __future__ import annotations

from decimal import Decimal

from apps.fund_management.models import PayInPackage
from apps.fund_management.package_gateways import (
    checkout_option_key as gateway_checkout_option_key,
    package_gateway_links_queryset,
)
from apps.fund_management.package_qr_accounts import (
    checkout_qr_option_key,
    package_qr_links_queryset,
)
from apps.fund_management.rail_fees import effective_link_fee, gateway_floor_pct, qr_floor_pct
from apps.fund_management.qr_limits import qr_limit_context, qr_usage_map_24h
from apps.fund_management.services import get_user_accessible_packages


def _serialize_gateway_option(
    *, package: PayInPackage, gateway, is_default: bool, sort_order: int, link_fee=None
) -> dict:
    eff = effective_link_fee(package, link_fee)
    return {
        'option_key': gateway_checkout_option_key(package.pk, gateway.id),
        'rail_type': 'gateway',
        'package_id': package.pk,
        'gateway_id': gateway.id,
        'qr_account_id': None,
        'id': gateway.id,
        'name': gateway.name,
        'status': gateway.status,
        'is_default': is_default,
        'sort_order': sort_order,
        'min_amount': str(package.min_amount),
        'max_amount_per_txn': str(package.max_amount_per_txn),
        'gateway_fee_pct': str(eff),
        'min_gateway_fee_pct': str(gateway_floor_pct(gateway)),
        'disabled': gateway.status != 'active',
        'disabled_reason': '' if gateway.status == 'active' else 'Gateway unavailable',
    }


def _serialize_qr_option(
    *,
    package: PayInPackage,
    qr,
    is_default: bool,
    sort_order: int,
    usage_map: dict[int, Decimal],
    request=None,
    link_fee=None,
) -> dict:
    used = usage_map.get(qr.pk, Decimal('0'))
    limit_ctx = qr_limit_context(qr, used=used)
    remaining = Decimal(limit_ctx['remaining_daily_limit'])
    min_amt = package.min_amount
    disabled = qr.status != 'active' or remaining < min_amt
    disabled_reason = ''
    if qr.status != 'active':
        disabled_reason = 'QR inactive'
    elif remaining <= 0:
        disabled_reason = '24-hour limit reached'
    elif remaining < min_amt:
        disabled_reason = 'Insufficient remaining limit for minimum amount'

    qr_image_url = ''
    if qr.qr_image:
        try:
            url = qr.qr_image.url
            if request and hasattr(request, 'build_absolute_uri'):
                qr_image_url = request.build_absolute_uri(url)
            else:
                qr_image_url = url
        except Exception:
            qr_image_url = ''

    per_txn_max = qr.max_per_txn
    effective_max = package.max_amount_per_txn
    if per_txn_max is not None and per_txn_max < effective_max:
        effective_max = per_txn_max
    if remaining < effective_max:
        effective_max = remaining

    eff = effective_link_fee(package, link_fee)
    return {
        'option_key': checkout_qr_option_key(package.pk, qr.id),
        'rail_type': 'qr',
        'package_id': package.pk,
        'gateway_id': None,
        'qr_account_id': qr.id,
        'id': qr.id,
        'name': qr.display_name,
        'status': qr.status,
        'is_default': is_default,
        'sort_order': sort_order,
        'min_amount': str(package.min_amount),
        'max_amount_per_txn': str(effective_max),
        'gateway_fee_pct': str(eff),
        'min_gateway_fee_pct': str(qr_floor_pct(qr)),
        'account_display_name': qr.account_display_name or '',
        'upi_vpa': qr.upi_vpa or '',
        'qr_image_url': qr_image_url,
        'daily_limit': limit_ctx['daily_limit'],
        'daily_used': limit_ctx['daily_used'],
        'remaining_daily_limit': limit_ctx['remaining_daily_limit'],
        'disabled': disabled,
        'disabled_reason': disabled_reason,
    }


def list_payin_checkout_options_for_user(user, request=None) -> list[dict]:
    """Flatten gateway + QR checkout rails across packages assigned to the user."""
    options: list[dict] = []
    packages = list(get_user_accessible_packages(user))

    all_qr_ids: list[int] = []
    for package in packages:
        for link in package_qr_links_queryset(package):
            if link.qr_account_id:
                all_qr_ids.append(link.qr_account_id)
    usage_map = qr_usage_map_24h(list(set(all_qr_ids)))

    for package in packages:
        gw_links = package_gateway_links_queryset(package)
        if gw_links.exists():
            for link in gw_links:
                gateway = link.payment_gateway
                if not gateway:
                    continue
                options.append(
                    _serialize_gateway_option(
                        package=package,
                        gateway=gateway,
                        is_default=link.is_default,
                        sort_order=link.sort_order,
                        link_fee=link.gateway_fee_pct,
                    )
                )
        elif package.payment_gateway_id and package.payment_gateway:
            options.append(
                _serialize_gateway_option(
                    package=package,
                    gateway=package.payment_gateway,
                    is_default=True,
                    sort_order=0,
                )
            )

        qr_links = package_qr_links_queryset(package)
        for link in qr_links:
            qr = link.qr_account
            if not qr:
                continue
            options.append(
                _serialize_qr_option(
                    package=package,
                    qr=qr,
                    is_default=link.is_default,
                    sort_order=link.sort_order,
                    usage_map=usage_map,
                    request=request,
                    link_fee=link.gateway_fee_pct,
                )
            )

    options.sort(
        key=lambda row: (
            0 if row.get('is_default') else 1,
            0 if row.get('rail_type') == 'gateway' else 1,
            row.get('sort_order', 0),
            row.get('name') or '',
            row.get('option_key') or '',
        )
    )
    return options
