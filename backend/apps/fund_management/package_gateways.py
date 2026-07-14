"""
Pay-in package ↔ payment gateway linking and resolution (execution rail only).
"""
from __future__ import annotations

from typing import Optional

from apps.admin_panel.models import PaymentGateway
from apps.fund_management.models import PayInPackage, PayInPackageGateway


def sync_package_gateway_links(
    package: PayInPackage,
    gateway_ids: list[int],
    *,
    default_gateway_id: Optional[int] = None,
) -> None:
    """
    Replace active gateway links for a package. Updates legacy package.payment_gateway FK
    to the default (or first) gateway for backward compatibility.
    """
    gateway_ids = [int(g) for g in gateway_ids if g is not None]
    seen = set()
    ordered_ids = []
    for gid in gateway_ids:
        if gid not in seen:
            seen.add(gid)
            ordered_ids.append(gid)

    PayInPackageGateway.objects.filter(package=package).delete()

    default_id = default_gateway_id
    if default_id is not None:
        default_id = int(default_id)
        if default_id not in ordered_ids:
            default_id = ordered_ids[0] if ordered_ids else None
    elif ordered_ids:
        default_id = ordered_ids[0]

    for sort_order, gid in enumerate(ordered_ids):
        PayInPackageGateway.objects.create(
            package=package,
            payment_gateway_id=gid,
            is_active=True,
            is_default=(gid == default_id),
            sort_order=sort_order,
        )

    primary = PaymentGateway.objects.filter(id=default_id).first() if default_id else None
    if package.payment_gateway_id != (primary.pk if primary else None):
        package.payment_gateway = primary
        package.save(update_fields=['payment_gateway', 'updated_at'])


def package_gateway_links_queryset(package: PayInPackage):
    return (
        PayInPackageGateway.objects.filter(package=package, is_deleted=False, is_active=True)
        .select_related('payment_gateway')
        .order_by('-is_default', 'sort_order', 'id')
    )


def list_checkout_gateways_for_package(package: PayInPackage):
    """Active linked gateways that are also active at PSP config level."""
    links = package_gateway_links_queryset(package)
    if links.exists():
        return [
            link.payment_gateway
            for link in links
            if link.payment_gateway and link.payment_gateway.status == 'active'
        ]
    if package.payment_gateway_id and package.payment_gateway.status == 'active':
        return [package.payment_gateway]
    return []


def checkout_option_key(package_id: int, gateway_id: int) -> str:
    return f'{package_id}:{gateway_id}'


def _serialize_checkout_option(
    *,
    package: PayInPackage,
    gateway: PaymentGateway,
    is_default: bool,
    sort_order: int,
) -> dict:
    return {
        'option_key': checkout_option_key(package.pk, gateway.id),
        'package_id': package.pk,
        'gateway_id': gateway.id,
        'id': gateway.id,
        'name': gateway.name,
        'status': gateway.status,
        'is_default': is_default,
        'sort_order': sort_order,
        'min_amount': str(package.min_amount),
        'max_amount_per_txn': str(package.max_amount_per_txn),
    }


def list_payin_checkout_options_for_user(user) -> list[dict]:
    """
    Flatten all checkout gateways across packages assigned to the user.
    Package is kept server-side for quotes/orders; UI shows gateway names only.
    """
    from apps.fund_management.services import get_user_accessible_packages

    options: list[dict] = []
    for package in get_user_accessible_packages(user):
        links = package_gateway_links_queryset(package)
        if links.exists():
            for link in links:
                gateway = link.payment_gateway
                if not gateway or gateway.status != 'active':
                    continue
                options.append(
                    _serialize_checkout_option(
                        package=package,
                        gateway=gateway,
                        is_default=link.is_default,
                        sort_order=link.sort_order,
                    )
                )
            continue
        if package.payment_gateway_id and package.payment_gateway.status == 'active':
            options.append(
                _serialize_checkout_option(
                    package=package,
                    gateway=package.payment_gateway,
                    is_default=True,
                    sort_order=0,
                )
            )

    options.sort(
        key=lambda row: (
            0 if row.get('is_default') else 1,
            row.get('sort_order', 0),
            row.get('name') or '',
            row.get('option_key') or '',
        )
    )
    return options


def resolve_payment_gateway_for_order(
    package: PayInPackage,
    gateway_id: Optional[int] = None,
) -> PaymentGateway:
    """
    Validate and return the PaymentGateway to use for create-order / verify.
    """
    allowed = list_checkout_gateways_for_package(package)
    allowed_by_id = {g.id: g for g in allowed}

    if gateway_id is not None:
        gw = allowed_by_id.get(int(gateway_id))
        if not gw:
            link_exists = PayInPackageGateway.objects.filter(
                package=package,
                payment_gateway_id=gateway_id,
                is_deleted=False,
            ).exists()
            if link_exists:
                raise ValueError('Selected payment gateway is not available. Try another gateway.')
            raise ValueError('Payment gateway is not linked to this package.')
        return gw

    default_link = (
        PayInPackageGateway.objects.filter(
            package=package,
            is_deleted=False,
            is_active=True,
            is_default=True,
        )
        .select_related('payment_gateway')
        .first()
    )
    if default_link and default_link.payment_gateway.status == 'active':
        return default_link.payment_gateway

    if allowed:
        return allowed[0]

    if package.payment_gateway_id and package.payment_gateway.status == 'active':
        return package.payment_gateway

    raise ValueError('No active payment gateway is configured for this package.')


def serialize_package_gateways(package: PayInPackage) -> list[dict]:
    links = package_gateway_links_queryset(package)
    if not links.exists() and package.payment_gateway_id:
        pg = package.payment_gateway
        return [
            {
                'id': pg.id,
                'name': pg.name,
                'status': pg.status,
                'is_default': True,
                'sort_order': 0,
            }
        ]
    out = []
    for link in links:
        pg = link.payment_gateway
        if not pg:
            continue
        out.append(
            {
                'id': pg.id,
                'name': pg.name,
                'status': pg.status,
                'is_default': link.is_default,
                'sort_order': link.sort_order,
            }
        )
    return out
