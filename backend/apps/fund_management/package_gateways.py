"""
Pay-in package ↔ payment gateway linking and resolution (execution rail only).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from apps.admin_panel.models import PaymentGateway
from apps.fund_management.models import PayInPackage, PayInPackageGateway
from apps.fund_management.rail_fees import effective_link_fee, gateway_floor_pct


def sync_package_gateway_links(
    package: PayInPackage,
    gateway_ids: list[int],
    *,
    default_gateway_id: Optional[int] = None,
    gateway_fees: Optional[dict[int, Decimal | None]] = None,
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

    fee_map = gateway_fees or {}
    default_pkg_fee = Decimal(str(package.gateway_fee_pct))

    for sort_order, gid in enumerate(ordered_ids):
        raw_fee = fee_map.get(gid)
        link_fee = None
        if raw_fee is not None and raw_fee != '':
            link_fee = Decimal(str(raw_fee))
        else:
            gw = PaymentGateway.objects.filter(pk=gid).first()
            if gw:
                link_fee = max(default_pkg_fee, gateway_floor_pct(gw))

        PayInPackageGateway.objects.create(
            package=package,
            payment_gateway_id=gid,
            is_active=True,
            is_default=(gid == default_id),
            sort_order=sort_order,
            gateway_fee_pct=link_fee,
        )

    primary = PaymentGateway.objects.filter(id=default_id).first() if default_id else None
    if package.payment_gateway_id != (primary.pk if primary else None):
        package.payment_gateway = primary
        package.save(update_fields=['payment_gateway', 'updated_at'])


def package_gateway_links_queryset(package: PayInPackage):
    """
    Active gateway links for a package.

    Prefer prefetched ``package_gateways`` (from get_user_accessible_packages) to
    avoid an extra SELECT per package during checkout.
    """
    cache = getattr(package, '_prefetched_objects_cache', None) or {}
    if 'package_gateways' in cache:
        return list(package.package_gateways.all())
    return list(
        PayInPackageGateway.objects.filter(package=package, is_deleted=False, is_active=True)
        .select_related('payment_gateway', 'payment_gateway__api_master')
        .order_by('-is_default', 'sort_order', 'id')
    )


def list_checkout_gateways_for_package(package: PayInPackage):
    """Active linked gateways that are also active at PSP config level."""
    links = package_gateway_links_queryset(package)
    if links:
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
    link_fee=None,
) -> dict:
    eff = effective_link_fee(package, link_fee)
    return {
        'option_key': checkout_option_key(package.pk, gateway.id),
        'rail_type': 'gateway',
        'package_id': package.pk,
        'gateway_id': gateway.id,
        'id': gateway.id,
        'name': gateway.name,
        'status': gateway.status,
        'is_default': is_default,
        'sort_order': sort_order,
        'min_amount': str(package.min_amount),
        'max_amount_per_txn': str(package.max_amount_per_txn),
        'gateway_fee_pct': str(eff),
        'min_gateway_fee_pct': str(gateway_floor_pct(gateway)),
    }


def list_payin_checkout_options_for_user(user, request=None) -> list[dict]:
    """
    Flatten all checkout gateways across packages assigned to the user.
    Delegates to checkout_options (gateways + QR rails).
    """
    from apps.fund_management.checkout_options import list_payin_checkout_options_for_user as _merged

    return _merged(user, request=request)


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
    if not links and package.payment_gateway_id:
        pg = package.payment_gateway
        eff = effective_link_fee(package, None)
        return [
            {
                'id': pg.id,
                'name': pg.name,
                'status': pg.status,
                'is_default': True,
                'sort_order': 0,
                'charge_rate': str(gateway_floor_pct(pg)),
                'gateway_fee_pct': None,
                'effective_gateway_fee_pct': str(eff),
            }
        ]
    out = []
    for link in links:
        pg = link.payment_gateway
        if not pg:
            continue
        eff = effective_link_fee(package, link.gateway_fee_pct)
        out.append(
            {
                'id': pg.id,
                'name': pg.name,
                'status': pg.status,
                'is_default': link.is_default,
                'sort_order': link.sort_order,
                'charge_rate': str(gateway_floor_pct(pg)),
                'gateway_fee_pct': str(link.gateway_fee_pct) if link.gateway_fee_pct is not None else None,
                'effective_gateway_fee_pct': str(eff),
            }
        )
    return out
