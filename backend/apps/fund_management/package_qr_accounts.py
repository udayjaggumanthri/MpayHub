"""Pay-in package ↔ QR account linking (execution rail only)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from apps.fund_management.models import PayInPackage, PayInPackageQrLink, PayInQrAccount
from apps.fund_management.rail_fees import effective_link_fee, qr_floor_pct


def sync_package_qr_links(
    package: PayInPackage,
    qr_account_ids: list[int],
    *,
    default_qr_account_id: Optional[int] = None,
    qr_fees: Optional[dict[int, Decimal | None]] = None,
) -> None:
    qr_account_ids = [int(q) for q in qr_account_ids if q is not None]
    seen = set()
    ordered_ids = []
    for qid in qr_account_ids:
        if qid not in seen:
            seen.add(qid)
            ordered_ids.append(qid)

    PayInPackageQrLink.objects.filter(package=package).delete()

    default_id = default_qr_account_id
    if default_id is not None:
        default_id = int(default_id)
        if default_id not in ordered_ids:
            default_id = ordered_ids[0] if ordered_ids else None
    elif ordered_ids:
        default_id = ordered_ids[0]

    fee_map = qr_fees or {}
    default_pkg_fee = Decimal(str(package.gateway_fee_pct))

    for sort_order, qid in enumerate(ordered_ids):
        raw_fee = fee_map.get(qid)
        link_fee = None
        if raw_fee is not None and raw_fee != '':
            link_fee = Decimal(str(raw_fee))
        else:
            qr = PayInQrAccount.objects.filter(pk=qid).first()
            if qr:
                link_fee = max(default_pkg_fee, qr_floor_pct(qr))

        PayInPackageQrLink.objects.create(
            package=package,
            qr_account_id=qid,
            is_active=True,
            is_default=(qid == default_id),
            sort_order=sort_order,
            gateway_fee_pct=link_fee,
        )


def package_qr_links_queryset(package: PayInPackage):
    """
    Active QR links for a package.

    Prefer prefetched ``package_qr_links`` when present (checkout N+1 avoidance).
    """
    cache = getattr(package, '_prefetched_objects_cache', None) or {}
    if 'package_qr_links' in cache:
        return list(package.package_qr_links.all())
    return list(
        PayInPackageQrLink.objects.filter(package=package, is_deleted=False, is_active=True)
        .select_related('qr_account')
        .order_by('-is_default', 'sort_order', 'id')
    )


def list_checkout_qr_for_package(package: PayInPackage) -> list[PayInQrAccount]:
    links = package_qr_links_queryset(package)
    return [
        link.qr_account
        for link in links
        if link.qr_account and link.qr_account.status == 'active'
    ]


def checkout_qr_option_key(package_id: int, qr_account_id: int) -> str:
    return f'q:{package_id}:{qr_account_id}'


def serialize_package_qr_accounts(package: PayInPackage) -> list[dict]:
    links = package_qr_links_queryset(package)
    out = []
    for link in links:
        qr = link.qr_account
        if not qr:
            continue
        eff = effective_link_fee(package, link.gateway_fee_pct)
        out.append(
            {
                'id': qr.id,
                'name': qr.display_name,
                'status': qr.status,
                'is_default': link.is_default,
                'sort_order': link.sort_order,
                'charge_rate': str(qr_floor_pct(qr)),
                'gateway_fee_pct': str(link.gateway_fee_pct) if link.gateway_fee_pct is not None else None,
                'effective_gateway_fee_pct': str(eff),
            }
        )
    return out


def resolve_qr_account_for_package(
    package: PayInPackage,
    qr_account_id: int,
) -> PayInQrAccount:
    link = (
        PayInPackageQrLink.objects.filter(
            package=package,
            qr_account_id=qr_account_id,
            is_deleted=False,
            is_active=True,
        )
        .select_related('qr_account')
        .first()
    )
    if not link or not link.qr_account:
        raise ValueError('QR account is not linked to this package.')
    qr = link.qr_account
    if qr.status != 'active':
        raise ValueError('Selected QR account is not available. Try another payment method.')
    return qr
