"""Per-rail gateway fee resolution and floor validation for pay-in packages."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from apps.admin_panel.models import PaymentGateway
from apps.fund_management.models import PayInPackage, PayInPackageGateway, PayInPackageQrLink, PayInQrAccount


def effective_link_fee(package: PayInPackage, link_fee) -> Decimal:
    if link_fee is not None and link_fee != '':
        return Decimal(str(link_fee))
    return Decimal(str(package.gateway_fee_pct))


def gateway_floor_pct(gateway: PaymentGateway) -> Decimal:
    return Decimal(str(getattr(gateway, 'charge_rate', 0) or 0))


def qr_floor_pct(qr: PayInQrAccount) -> Decimal:
    return Decimal(str(getattr(qr, 'charge_rate', 0) or 0))


def resolve_rail_gateway_fee_pct(
    package: PayInPackage,
    *,
    gateway_id: Optional[int] = None,
    qr_account_id: Optional[int] = None,
) -> Decimal:
    """Effective gateway fee % for the selected checkout rail."""
    if qr_account_id is not None:
        link = (
            PayInPackageQrLink.objects.filter(
                package=package,
                qr_account_id=int(qr_account_id),
                is_deleted=False,
                is_active=True,
            )
            .first()
        )
        if link:
            return effective_link_fee(package, link.gateway_fee_pct)

    if gateway_id is not None:
        link = (
            PayInPackageGateway.objects.filter(
                package=package,
                payment_gateway_id=int(gateway_id),
                is_deleted=False,
                is_active=True,
            )
            .first()
        )
        if link:
            return effective_link_fee(package, link.gateway_fee_pct)

    return Decimal(str(package.gateway_fee_pct))


def max_package_gateway_fee_pct(package: PayInPackage) -> Decimal:
    """Highest effective gateway fee across all rails (worst case for total deduction cap)."""
    fees = [Decimal(str(package.gateway_fee_pct))]
    for link in PayInPackageGateway.objects.filter(package=package, is_deleted=False, is_active=True):
        fees.append(effective_link_fee(package, link.gateway_fee_pct))
    for link in PayInPackageQrLink.objects.filter(package=package, is_deleted=False, is_active=True):
        fees.append(effective_link_fee(package, link.gateway_fee_pct))
    return max(fees) if fees else Decimal(str(package.gateway_fee_pct))


def derive_provider_from_gateway(gateway: Optional[PaymentGateway]) -> str:
    if not gateway:
        return 'mock'
    am = getattr(gateway, 'api_master', None)
    code = (getattr(am, 'provider_code', '') or '').lower() if am else ''
    if 'payu' in code:
        return 'payu'
    if 'razorpay' in code or code.startswith('rz'):
        return 'razorpay'
    name = (gateway.name or '').lower()
    if 'payu' in name:
        return 'payu'
    if 'razorpay' in name or 'razo' in name:
        return 'razorpay'
    return 'razorpay'


def validate_rail_fee_floor(
    *,
    name: str,
    fee_pct: Decimal,
    floor_pct: Decimal,
    admin_label: str,
) -> Optional[str]:
    if fee_pct < floor_pct:
        return (
            f'Gateway fee for {name} cannot be below {floor_pct}% — check {admin_label}.'
        )
    return None


def validate_package_rail_fees(
    package: PayInPackage,
    gateway_specs: list[dict],
    qr_specs: list[dict],
) -> list[str]:
    """Return list of validation error messages for per-rail fees."""
    errors: list[str] = []
    default_fee = Decimal(str(package.gateway_fee_pct))

    for spec in gateway_specs:
        gid = int(spec['payment_gateway_id'])
        gw = PaymentGateway.objects.filter(pk=gid).first()
        if not gw:
            continue
        fee = effective_link_fee(package, spec.get('gateway_fee_pct'))
        if spec.get('gateway_fee_pct') is None and fee == default_fee:
            fee = max(fee, gateway_floor_pct(gw))
        msg = validate_rail_fee_floor(
            name=gw.name,
            fee_pct=fee,
            floor_pct=gateway_floor_pct(gw),
            admin_label='Payment Gateways admin',
        )
        if msg:
            errors.append(msg)

    for spec in qr_specs:
        qid = int(spec['qr_account_id'])
        qr = PayInQrAccount.objects.filter(pk=qid).first()
        if not qr:
            continue
        fee = effective_link_fee(package, spec.get('gateway_fee_pct'))
        if spec.get('gateway_fee_pct') is None and fee == default_fee:
            fee = max(fee, qr_floor_pct(qr))
        msg = validate_rail_fee_floor(
            name=qr.display_name,
            fee_pct=fee,
            floor_pct=qr_floor_pct(qr),
            admin_label='QR accounts admin',
        )
        if msg:
            errors.append(msg)

    return errors
