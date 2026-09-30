"""
Fund management business logic services.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import IntegrityError
from django.db import transaction as db_transaction

from apps.core.roles import is_platform_operator
from apps.admin_panel.models import PaymentGateway, PayoutGateway
from apps.bank_accounts.models import BankAccount
from apps.contacts.models import Contact
from apps.authentication.models import User
from apps.core.exceptions import InsufficientBalance, TransactionFailed
from apps.core.utils import decrypt_secret_payload
from apps.core.utils import generate_service_id
from apps.fund_management.models import LoadMoney, PayInPackage, Payout
from apps.fund_management.money_utils import money_q
from apps.fund_management.payin_distribution import _compute_payin_distribution
from apps.fund_management.payin_settlement import (
    _passbook_credit,
    _payment_capture_from_razorpay_payment,
    finalize_payin_success,
)
from apps.transactions.agent_snapshot import (
    card_last4_from_payment_meta,
    passbook_initiator_db_fields,
    transaction_agent_db_fields,
)
from apps.transactions.models import PassbookEntry, Transaction
from apps.wallets.models import Wallet

logger = logging.getLogger(__name__)


def calculate_service_charge(amount, gateway_id=None, transaction_type='payin'):
    """
    Legacy: single percentage charge (gateway row or default).
    """
    amount = money_q(Decimal(str(amount)))
    if gateway_id:
        try:
            gateway = PaymentGateway.objects.get(id=gateway_id, status='active')
            charge_rate = Decimal(str(gateway.charge_rate)) / Decimal('100')
            charge = money_q(amount * charge_rate)
            net_amount = money_q(amount - charge)
            return {
                'charge_rate': gateway.charge_rate,
                'charge': charge,
                'net_amount': net_amount,
            }
        except PaymentGateway.DoesNotExist:
            pass

    if transaction_type == 'payin':
        charge_rate = Decimal('0.01')
    else:
        charge_rate = Decimal('0.001')

    charge = money_q(amount * charge_rate)
    net_amount = money_q(amount - charge)
    return {
        'charge_rate': float(charge_rate * 100),
        'charge': charge,
        'net_amount': net_amount,
    }


def _payout_slab_charge_global(amount: Decimal) -> Decimal:
    """Legacy two-tier charge from PayoutSlabConfig or Django settings (no user context)."""
    amount = money_q(amount)
    low_max = getattr(settings, 'PAYOUT_SLAB_LOW_MAX', Decimal('24999'))
    low_c = getattr(settings, 'PAYOUT_CHARGE_LOW', Decimal('7'))
    high_c = getattr(settings, 'PAYOUT_CHARGE_HIGH', Decimal('15'))
    try:
        from apps.admin_panel.models import PayoutSlabConfig

        cfg = (
            PayoutSlabConfig.objects.filter(is_active=True)
            .only('low_max_amount', 'low_charge', 'high_charge')
            .order_by('-updated_at', '-id')
            .first()
        )
        if cfg:
            low_max = Decimal(str(cfg.low_max_amount))
            low_c = money_q(cfg.low_charge)
            high_c = money_q(cfg.high_charge)
    except Exception:
        pass
    if amount <= low_max:
        return low_c
    return high_c


def payout_slab_charge(amount: Decimal) -> Decimal:
    """Backward-compatible global slab charge (tests and fallback)."""
    return _payout_slab_charge_global(amount)


def _max_payout_eligible_global(balance: Decimal) -> Decimal:
    """Max payout send amount for legacy two-tier global config."""
    balance = money_q(Decimal(str(balance)))
    if balance <= 0:
        return Decimal('0')
    low_max = getattr(settings, 'PAYOUT_SLAB_LOW_MAX', Decimal('24999'))
    low_c = getattr(settings, 'PAYOUT_CHARGE_LOW', Decimal('7'))
    high_c = getattr(settings, 'PAYOUT_CHARGE_HIGH', Decimal('15'))
    try:
        from apps.admin_panel.models import PayoutSlabConfig

        cfg = (
            PayoutSlabConfig.objects.filter(is_active=True)
            .only('low_max_amount', 'low_charge', 'high_charge')
            .order_by('-updated_at', '-id')
            .first()
        )
        if cfg:
            low_max = Decimal(str(cfg.low_max_amount))
            low_c = money_q(cfg.low_charge)
            high_c = money_q(cfg.high_charge)
    except Exception:
        pass
    cand_low = Decimal('0')
    if balance >= low_c:
        cand_low = money_q(min(low_max, balance - low_c))
        if cand_low < 0:
            cand_low = Decimal('0')
    cand_high = Decimal('0')
    threshold = low_max + Decimal('1')
    if balance >= high_c + threshold:
        ch = money_q(balance - high_c)
        if ch >= threshold:
            cand_high = ch
    return max(cand_low, cand_high)


def max_payout_eligible(balance: Decimal) -> Decimal:
    """Backward-compatible global max eligible (no user context)."""
    return _max_payout_eligible_global(balance)


def quote_payin(
    package: PayInPackage,
    gross: Decimal,
    payer_user: Optional[User] = None,
    *,
    gateway_id: int | None = None,
    qr_account_id: int | None = None,
) -> dict:
    """Build line-item breakdown; net = gross - sum(deduction slices). Pass payer_user for upline-aware admin absorption."""
    from apps.fund_management.rail_fees import resolve_rail_gateway_fee_pct

    rail_fee = resolve_rail_gateway_fee_pct(
        package, gateway_id=gateway_id, qr_account_id=qr_account_id
    )
    dist = _compute_payin_distribution(package, gross, payer_user, gateway_fee_pct=rail_fee)
    return {
        'snapshot': dist['snapshot'],
        'net_credit': dist['net_credit'],
        'total_deduction': dist['total_deduction'],
        'retailer_commission': dist['retailer_commission'],
        'retailer_share_absorbed_to_admin': dist['retailer_absorbed_to_admin'],
        'lines': dist['lines'],
    }


def payin_quote_api_payload_for_user(user, q: dict) -> dict:
    """
    Serialize quote_payin() for HTTP responses.
    Commission line-items, hierarchy notes, and aggregate deduction fields are Admin-only.
    Non-admins still receive net_credit (and empty lines/breakdown) so checkout can proceed.
    """
    if is_platform_operator(user):
        return {
            'breakdown': q['snapshot'],
            'lines': q['lines'],
            'net_credit': str(q['net_credit']),
            'total_deduction': str(q['total_deduction']),
            'retailer_commission': str(q['retailer_commission']),
            'retailer_share_absorbed_to_admin': str(q['retailer_share_absorbed_to_admin']),
        }
    return {
        'breakdown': {},
        'lines': [],
        'net_credit': str(q['net_credit']),
    }


def _api_master_for_payin_razorpay(package: PayInPackage, payment_gateway=None):
    """
    Resolve which ApiMaster supplies Razorpay keys for this pay-in package.

    1) Selected payment gateway's linked API Master (payments) — preferred for multi-provider setups.
    2) Else, first payments-type row with a Razorpay-like provider_code (is_default / priority order).
       This matches ops who configure credentials only in API Master without re-linking the gateway row.
    """
    from apps.integrations.models import ApiMaster
    from apps.integrations.razorpay_orders import is_razorpay_like_provider_code

    pg = payment_gateway or getattr(package, 'payment_gateway', None)
    if pg and getattr(pg, 'api_master_id', None):
        am = pg.api_master
        if (
            am
            and am.provider_type == 'payments'
            and is_razorpay_like_provider_code(am.provider_code)
        ):
            return am
    if str(package.provider or '') != 'razorpay':
        return None
    qs = (
        ApiMaster.objects.filter(provider_type='payments', is_deleted=False)
        .order_by('-is_default', '-priority', 'pk')
    )
    for m in qs:
        if is_razorpay_like_provider_code(m.provider_code):
            return m
    return None


def _razorpay_keypair_for_payin_package(package: PayInPackage, payment_gateway=None):
    """Resolved Razorpay key_id + key_secret from API Master (live read); optional .env fallback if unset."""
    from apps.integrations.razorpay_orders import (
        extract_razorpay_key_pair_from_secrets,
        resolve_razorpay_credentials,
    )

    key_id = None
    key_secret = None
    api_master = _api_master_for_payin_razorpay(package, payment_gateway=payment_gateway)
    if api_master:
        secrets = decrypt_secret_payload(api_master.secrets_encrypted or '')
        key_id, key_secret = extract_razorpay_key_pair_from_secrets(secrets)
        if not (key_id and key_secret) and (api_master.secrets_encrypted or '').strip():
            logger.warning(
                'Pay-in Razorpay: API Master id=%s (%s) has encrypted secrets but key_id/key_secret '
                'pair could not be read; check key names (key_id / key_secret) or .env fallback.',
                api_master.pk,
                api_master.provider_code,
            )
    return resolve_razorpay_credentials(key_id, key_secret)


def create_payin_order(
    user,
    *,
    package_id: int,
    gross: Decimal,
    contact_id: int,
    gateway_id: int | None = None,
):
    """Create pending LoadMoney; call Razorpay outside DB transaction when needed."""
    from apps.fund_management.package_gateways import resolve_payment_gateway_for_order

    package = (
        PayInPackage.objects.filter(id=package_id, is_active=True, is_deleted=False)
        .select_related('payment_gateway', 'payment_gateway__api_master')
        .first()
    )
    if not package:
        raise ValueError('Invalid or inactive package')
    accessible = get_user_accessible_packages(user)
    if not accessible.filter(pk=package.pk).exists():
        raise ValueError('Package not available for your account')
    if package.provider == 'payu':
        raise TransactionFailed('PayU checkout is not enabled yet. Use a mock or Razorpay package.')

    try:
        selected_gateway = resolve_payment_gateway_for_order(package, gateway_id)
    except ValueError as exc:
        raise TransactionFailed(str(exc)) from exc

    contact = Contact.objects.filter(id=contact_id, user=user).first()
    if not contact:
        raise ValueError('Contact not found')

    q = quote_payin(package, gross, user, gateway_id=selected_gateway.id)

    lm = None
    last_integrity: IntegrityError | None = None
    for attempt in range(2):
        tid = generate_service_id('load_money')
        try:
            with db_transaction.atomic():
                lm = LoadMoney.objects.create(
                    user=user,
                    package=package,
                    payment_gateway=selected_gateway,
                    amount=money_q(gross),
                    gateway=selected_gateway.name or str(package.code),
                    charge=q['total_deduction'],
                    net_credit=q['net_credit'],
                    fee_breakdown_snapshot=q['snapshot'],
                    customer_name=contact.name,
                    customer_email=contact.email,
                    customer_phone=contact.phone,
                    status='PENDING',
                    transaction_id=tid,
                )
            break
        except IntegrityError as exc:
            last_integrity = exc
            logger.warning('LoadMoney create collision on transaction_id (attempt %s)', attempt)
    if lm is None:
        raise TransactionFailed(
            'Could not allocate a unique pay-in reference; please retry.'
        ) from last_integrity

    response = {
        'load_money_id': lm.id,
        'transaction_id': lm.transaction_id,
        'provider': package.provider,
        'payment_gateway_id': selected_gateway.id,
        'payment_gateway_name': selected_gateway.name,
        'amount': str(lm.amount),
        'currency': 'INR',
        'customer_name': contact.name,
        'customer_email': contact.email,
        'customer_phone': contact.phone,
        'fee_preview': q['snapshot'],
    }

    if package.provider == 'razorpay':
        from apps.integrations.razorpay_orders import create_order as rz_order

        checkout_key_id, checkout_key_secret = _razorpay_keypair_for_payin_package(
            package, payment_gateway=selected_gateway
        )

        order, err = rz_order(
            amount_inr=lm.amount,
            receipt=lm.transaction_id,
            notes={'txn': lm.transaction_id},
            key_id=checkout_key_id,
            key_secret=checkout_key_secret,
        )
        if err:
            LoadMoney.objects.filter(pk=lm.pk).update(
                failure_reason=str(err),
                status='FAILED',
            )
            lm.refresh_from_db()
            if str(err) == 'not_configured':
                raise TransactionFailed(
                    'Could not create payment order: Razorpay credentials are missing. '
                    'In API Master (Payments), add credentials with keys key_id and key_secret '
                    '(Key ID in the value for key_id, secret in the value for key_secret). '
                    'Link that API Master to the payment gateway if you use several providers, '
                    'or mark one Razorpay entry as default. Optional: set RAZORPAY_KEY_ID / '
                    'RAZORPAY_KEY_SECRET in the server environment.'
                )
            raise TransactionFailed(f'Could not create payment order: {err}')

        LoadMoney.objects.filter(pk=lm.pk).update(provider_order_id=order.get('id'))
        lm.refresh_from_db()
        response['razorpay'] = {
            'key_id': checkout_key_id,
            'order_id': lm.provider_order_id,
            'amount': order.get('amount'),
            'currency': order.get('currency', 'INR'),
        }
    else:
        response['mock'] = True
        response['message'] = 'Mock provider: call POST /fund-management/pay-in/complete-mock/ with transaction_id'

    if not is_platform_operator(user):
        response['fee_preview'] = {}

    try:
        from apps.notifications.services.dispatch import SmsNotificationService
        from apps.notifications.email_helpers import dispatch_user_email

        ctx = {
            'amount': str(lm.amount),
            'transaction_id': lm.transaction_id,
            'reference': lm.transaction_id,
        }
        SmsNotificationService.dispatch(
            'payin.pending',
            user.phone,
            ctx,
            user_id=user.pk,
            idempotency_key=f'payin:{lm.transaction_id}:PENDING',
        )
        dispatch_user_email(
            'payin.pending',
            user,
            ctx,
            idempotency_key=f'payin:{lm.transaction_id}:PENDING',
        )
    except Exception:
        pass

    return lm, response


@db_transaction.atomic
def complete_mock_payin(user, transaction_id: str):
    lm = (
        LoadMoney.objects.select_for_update()
        .filter(transaction_id=transaction_id, user=user)
        .first()
    )
    if not lm:
        raise ValueError('Load money record not found')
    if not lm.package or lm.package.provider != 'mock':
        raise ValueError('Only mock packages can be completed via this endpoint')
    if lm.status != 'PENDING':
        return lm
    fake_pay_id = f'mockpay_{lm.transaction_id}'
    return finalize_payin_success(
        lm,
        provider_payment_id=fake_pay_id,
        gateway_reference=fake_pay_id,
        payment_method='mock',
        payment_meta={'channel': 'mock'},
    )


@db_transaction.atomic
def verify_and_finalize_razorpay_payin(
    user,
    *,
    transaction_id: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
):
    """
    After Razorpay Checkout success: verify HMAC + fetch payment status, then credit wallet.
    Use this on localhost or when webhooks are delayed; production should still configure webhooks.
    """
    from apps.integrations.razorpay_orders import (
        fetch_razorpay_payment_until_captured,
        verify_razorpay_checkout_signature,
    )

    # PostgreSQL does not allow FOR UPDATE on nullable-side OUTER JOINs.
    # Keep the row lock on LoadMoney only, then lazily read related fields.
    lm = (
        LoadMoney.objects.select_for_update()
        .filter(transaction_id=transaction_id, user=user)
        .first()
    )
    if not lm:
        raise ValueError('No pay-in record found for this reference.')
    if lm.status == 'SUCCESS':
        return lm
    if lm.status != 'PENDING':
        raise ValueError('This pay-in can no longer be completed.')
    if not lm.package or lm.package.provider != 'razorpay':
        raise ValueError('This completion path is only for Razorpay pay-ins.')
    if (lm.provider_order_id or '') != str(razorpay_order_id).strip():
        raise ValueError('Razorpay order id does not match this transaction.')

    verify_gateway = lm.payment_gateway
    if verify_gateway is None and lm.package:
        verify_gateway = lm.package.payment_gateway
    key_id, key_secret = _razorpay_keypair_for_payin_package(lm.package, payment_gateway=verify_gateway)
    if not key_id or not key_secret:
        raise TransactionFailed('Razorpay credentials are not configured.')

    if not verify_razorpay_checkout_signature(
        str(razorpay_order_id).strip(),
        str(razorpay_payment_id).strip(),
        str(razorpay_signature).strip(),
        key_secret=key_secret,
    ):
        logger.warning(
            'Razorpay checkout signature failed: txn=%s order=%s payment=%s',
            transaction_id,
            razorpay_order_id,
            razorpay_payment_id,
        )
        raise TransactionFailed('Payment verification failed (invalid signature).')

    pay, fetch_err = fetch_razorpay_payment_until_captured(
        str(razorpay_payment_id).strip(), key_id=key_id, key_secret=key_secret
    )
    if fetch_err or not pay:
        raise TransactionFailed(
            fetch_err
            or 'Could not confirm a captured payment with Razorpay. '
            'If payment succeeded at Razorpay, try again in a few seconds or rely on the webhook.'
        )
    pay_status = str((pay or {}).get('status') or '').lower()
    if pay_status != 'captured':
        raise TransactionFailed(
            f'Payment could not be confirmed as captured (status={pay_status}). '
            'Retry verification shortly or ensure webhooks are configured.'
        )
    linked_order = (pay or {}).get('order_id') or ''
    if linked_order and linked_order != str(razorpay_order_id).strip():
        raise TransactionFailed('Payment does not belong to this order.')

    logger.info(
        'Pay-in Razorpay checkout verify OK: txn=%s payment_id=%s user_id=%s',
        transaction_id,
        razorpay_payment_id,
        user.pk,
    )
    rz_method, rz_meta = _payment_capture_from_razorpay_payment(pay)
    return finalize_payin_success(
        lm,
        provider_payment_id=str(razorpay_payment_id).strip(),
        gateway_reference=str(razorpay_payment_id).strip(),
        payment_method=rz_method or None,
        payment_meta=rz_meta or None,
    )


@db_transaction.atomic
def process_load_money(user, amount, gateway_id):
    """Legacy synchronous path: single gateway %; immediate success (no commission split)."""
    amount = money_q(Decimal(str(amount)))
    charge_info = calculate_service_charge(amount, gateway_id, 'payin')

    load_money = None
    last_integrity: IntegrityError | None = None
    for attempt in range(2):
        tid = generate_service_id('load_money')
        try:
            with db_transaction.atomic():
                load_money = LoadMoney.objects.create(
                    user=user,
                    amount=amount,
                    gateway=str(gateway_id or 'default'),
                    charge=charge_info['charge'],
                    net_credit=charge_info['net_amount'],
                    fee_breakdown_snapshot={
                        'legacy': True,
                        'gross': str(amount),
                        'charge': str(charge_info['charge']),
                        'net_credit': str(charge_info['net_amount']),
                    },
                    status='PENDING',
                    transaction_id=tid,
                )
            break
        except IntegrityError as exc:
            last_integrity = exc
            logger.warning('process_load_money LoadMoney id collision (attempt %s)', attempt)
    if load_money is None:
        raise TransactionFailed(
            'Could not allocate a unique load reference; please retry.'
        ) from last_integrity

    try:
        gateway_transaction_id = f"GTX{load_money.transaction_id}"
        load_money.gateway_transaction_id = gateway_transaction_id
        load_money.status = 'SUCCESS'
        load_money.save(update_fields=['gateway_transaction_id', 'status'])

        _passbook_credit(
            user,
            'main',
            'LOAD MONEY',
            load_money.transaction_id,
            f"LOAD MONEY (legacy), GATEWAY: {gateway_id or 'default'}, AMOUNT: {amount}, CHARGE: {charge_info['charge']}",
            charge_info['net_amount'],
            gateway_transaction_id,
            service_charge=charge_info['charge'],
            principal_amount=amount,
        )

        Transaction.objects.create(
            user=user,
            transaction_type='payin',
            amount=amount,
            charge=charge_info['charge'],
            net_amount=charge_info['net_amount'],
            status='SUCCESS',
            service_id=load_money.transaction_id,
            reference=gateway_transaction_id,
            service_family='payin',
            bank_txn_id=gateway_transaction_id[:191],
            **transaction_agent_db_fields(user),
        )

        try:
            from apps.fund_management.payin_settlement import _notify_payin_success

            _notify_payin_success(
                load_money,
                reference=gateway_transaction_id,
                gross=amount,
            )
        except Exception:
            pass

        return load_money
    except Exception as e:
        load_money.status = 'FAILED'
        load_money.failure_reason = str(e)
        load_money.save(update_fields=['status', 'failure_reason'])
        try:
            from apps.notifications.services.dispatch import SmsNotificationService
            from apps.notifications.email_helpers import dispatch_user_email

            ctx = {
                'amount': str(amount),
                'transaction_id': load_money.transaction_id,
                'reference': load_money.transaction_id,
                'reason': str(e)[:200],
            }
            SmsNotificationService.dispatch(
                'payin.failed',
                user.phone,
                ctx,
                user_id=user.pk,
                idempotency_key=f'payin:{load_money.transaction_id}:FAILED',
            )
            dispatch_user_email(
                'payin.failed',
                user,
                ctx,
                idempotency_key=f'payin:{load_money.transaction_id}:FAILED',
            )
        except Exception:
            pass
        raise TransactionFailed(f'Load money failed: {str(e)}') from e


def process_payout(
    user,
    bank_account_id,
    amount,
    gateway_id=None,
    transfer_mode: str = 'IMPS',
    **kwargs,
):
    """
    Real provider payout (hold until callback). Mock instant-SUCCESS path removed.
    Extra kwargs: beneficiary_location, purpose_code, lat, long, udf1, udf2, udf3.
    """
    from apps.fund_management.payout_orchestrator import process_payout as _orchestrate

    return _orchestrate(
        user,
        bank_account_id,
        amount,
        gateway_id=gateway_id,
        transfer_mode=transfer_mode,
        **kwargs,
    )


def get_available_gateways(user_role=None, gateway_type='payment'):
    """
    Returns active gateways. Access is now controlled via Package Assignment system,
    not role-based visibility.
    """
    if gateway_type == 'payment':
        return PaymentGateway.objects.filter(status='active')
    return PayoutGateway.objects.filter(status='active')


def list_active_pay_in_packages():
    return PayInPackage.objects.filter(is_active=True, is_deleted=False).order_by('sort_order', 'display_name')


# ─────────────────────────────────────────────────────────────────────────────
# Package Assignment System - Access Control Functions
# ─────────────────────────────────────────────────────────────────────────────

def get_user_accessible_packages(user: User):
    """
    Returns packages the user can access for pay-in:
    1. Packages explicitly assigned to the user
    2. If no explicit assignments exist, returns default package (if any)

    Admin users have access to ALL active packages.

    Prefetches active gateway/QR links so checkout can avoid N+1 per package.
    """
    from django.db.models import Prefetch

    from apps.fund_management.models import (
        PayInPackageGateway,
        PayInPackageQrLink,
        UserPackageAssignment,
    )

    gw_qs = (
        PayInPackageGateway.objects.filter(is_deleted=False, is_active=True)
        .select_related('payment_gateway', 'payment_gateway__api_master')
        .order_by('-is_default', 'sort_order', 'id')
    )
    qr_qs = (
        PayInPackageQrLink.objects.filter(is_deleted=False, is_active=True)
        .select_related('qr_account')
        .order_by('-is_default', 'sort_order', 'id')
    )

    def _with_links(qs):
        return qs.prefetch_related(
            Prefetch('package_gateways', queryset=gw_qs),
            Prefetch('package_qr_links', queryset=qr_qs),
        ).order_by('-is_default', 'sort_order', 'display_name')

    # Admin users can access all packages
    user_role = (getattr(user, 'role', None) or '').strip()
    if is_platform_operator(user_role):
        return _with_links(PayInPackage.objects.filter(is_active=True, is_deleted=False))

    # Check explicit assignments
    assigned_pkg_ids = UserPackageAssignment.objects.filter(
        user=user, is_deleted=False
    ).values_list('package_id', flat=True)

    if assigned_pkg_ids:
        return _with_links(
            PayInPackage.objects.filter(
                id__in=assigned_pkg_ids,
                is_active=True,
                is_deleted=False,
            )
        )

    # Fallback to default package
    return _with_links(
        PayInPackage.objects.filter(
            is_default=True,
            is_active=True,
            is_deleted=False,
        )
    )


def resolve_payout_package(user: User) -> Optional[PayInPackage]:
    """
    Single PayInPackage used for payout slab lookup: first row from the same ordered set
    as pay-in access (sort_order, display_name).
    """
    qs = get_user_accessible_packages(user)
    return qs.first()


def _payout_slab_breakdown_global(amount: Decimal) -> dict:
    """Legacy two-tier → charge only, commission 0 (safety net)."""
    amount = money_q(amount)
    charge = _payout_slab_charge_global(amount)
    return {
        'charge': money_q(charge),
        'commission': Decimal('0'),
        'total': money_q(charge),
    }


def payout_slab_breakdown_for_amount(amount: Decimal) -> dict:
    """
    Platform-wide slab match: charge + commission + total.

    Prefers ``PlatformPayoutSlabTier``; falls back to legacy two-tier config.
    """
    amount = money_q(Decimal(str(amount)))
    from apps.fund_management.models import PlatformPayoutSlabTier

    tiers = (
        PlatformPayoutSlabTier.objects.filter(is_deleted=False)
        .only('min_amount', 'max_amount', 'charge', 'commission', 'sort_order')
        .order_by('sort_order', 'min_amount')
    )
    if tiers.exists():
        for t in tiers:
            lo = money_q(t.min_amount)
            hi = money_q(t.max_amount) if t.max_amount is not None else None
            if amount < lo:
                continue
            if hi is not None and amount > hi:
                continue
            charge = money_q(t.charge or 0)
            commission = money_q(t.commission or 0)
            return {
                'charge': charge,
                'commission': commission,
                'total': money_q(charge + commission),
            }
        # Amount outside all bands — last open-ended tier or global fallback
        last = tiers.last()
        if last is not None and last.max_amount is None:
            charge = money_q(last.charge or 0)
            commission = money_q(last.commission or 0)
            return {
                'charge': charge,
                'commission': commission,
                'total': money_q(charge + commission),
            }
    return _payout_slab_breakdown_global(amount)


def payout_slab_breakdown_for_user(user: User, amount: Decimal) -> dict:
    """Platform slabs only (package tiers no longer used for payout pricing)."""
    del user  # API compatibility; pricing is platform-wide
    return payout_slab_breakdown_for_amount(amount)


def payout_flat_charge_for_package(package: Optional[PayInPackage], amount: Decimal) -> Decimal:
    """
    Backward-compatible total fee for amount (ignores package — platform slabs).
    """
    del package
    return payout_slab_breakdown_for_amount(amount)['total']


def payout_slab_charge_for_user(user: User, amount: Decimal) -> Decimal:
    """Total payout fee (charge + commission) for amount."""
    return payout_slab_breakdown_for_user(user, amount)['total']


def max_payout_eligible_for_user(user: User, balance: Decimal) -> Decimal:
    """
    Maximum payout principal such that principal + total_fee(principal) <= balance,
    using platform Charge+Commission tiers.
    """
    del user
    balance = money_q(Decimal(str(balance)))
    if balance <= 0:
        return Decimal('0')
    from apps.fund_management.models import PlatformPayoutSlabTier

    tiers = list(
        PlatformPayoutSlabTier.objects.filter(is_deleted=False).order_by('sort_order', 'min_amount')
    )
    if not tiers:
        return _max_payout_eligible_global(balance)
    best = Decimal('0')
    for t in tiers:
        total_fee = money_q((t.charge or 0) + (t.commission or 0))
        lo = money_q(t.min_amount)
        hi = money_q(t.max_amount) if t.max_amount is not None else None
        cap = money_q(balance - total_fee)
        if cap < lo:
            continue
        upper = min(cap, hi) if hi is not None else cap
        if upper >= lo and upper > best:
            best = upper
    return money_q(best)


def get_user_assigned_packages(user: User):
    """
    Returns packages explicitly assigned to a user (for admin/upline viewing).
    Does NOT include default fallback.
    """
    from apps.fund_management.models import UserPackageAssignment

    assigned_pkg_ids = UserPackageAssignment.objects.filter(
        user=user, is_deleted=False
    ).values_list('package_id', flat=True)

    return PayInPackage.objects.filter(
        id__in=assigned_pkg_ids,
        is_deleted=False,
    ).order_by('sort_order', 'display_name')


def can_user_assign_package(assigner: User, package_id: int) -> bool:
    """
    Only Admin may assign pay-in packages to users (package definition + assignment).
    """
    assigner_role = (getattr(assigner, 'role', None) or '').strip()
    if not is_platform_operator(assigner_role):
        return False
    return PayInPackage.objects.filter(id=package_id, is_active=True, is_deleted=False).exists()


def is_user_in_downline(senior: User, junior: User) -> bool:
    """
    Check if junior is in senior's direct downline hierarchy.
    Uses the parent chain to verify.
    """
    if senior.pk == junior.pk:
        return False
    
    senior_role = (getattr(senior, 'role', None) or '').strip()
    if is_platform_operator(senior_role):
        return True  # Admin can assign to anyone

    # Walk up the junior's parent chain
    current = junior
    visited = set()
    while current:
        if current.pk in visited:
            break
        visited.add(current.pk)
        
        parent = getattr(current, 'parent', None)
        if parent and parent.pk == senior.pk:
            return True
        current = parent
    
    return False


def assign_package_to_user(
    *,
    assigner: User,
    target_user: User,
    package_id: int,
) -> dict:
    """
    Assign a package to target_user.

    Admin only (validated via ``can_user_assign_package``).

    Validation:
    - Assigner must be Admin with access to the package
    - Target must be in assigner's downline (Admin may assign to any user)
    """
    from apps.fund_management.models import UserPackageAssignment

    # Validate package exists and is active
    package = PayInPackage.objects.filter(
        id=package_id, is_active=True, is_deleted=False
    ).first()
    if not package:
        return {'success': False, 'message': 'Package not found or inactive.', 'assignment': None}

    # Check assigner can assign this package
    if not can_user_assign_package(assigner, package_id):
        return {
            'success': False,
            'message': 'You do not have access to this package and cannot assign it.',
            'assignment': None,
        }

    # Check target is in assigner's downline
    assigner_role = (getattr(assigner, 'role', None) or '').strip()
    if not is_platform_operator(assigner_role) and not is_user_in_downline(assigner, target_user):
        return {
            'success': False,
            'message': 'You can only assign packages to users in your downline.',
            'assignment': None,
        }

    # Create or update assignment
    assignment, created = UserPackageAssignment.objects.update_or_create(
        user=target_user,
        package=package,
        defaults={
            'assigned_by': assigner,
            'is_deleted': False,
        },
    )

    if created:
        logger.info(
            'Package assigned: package=%s (%s) to user=%s by assigner=%s',
            package.pk,
            package.display_name,
            target_user.user_id,
            assigner.user_id,
        )
        return {
            'success': True,
            'message': f'Package "{package.display_name}" assigned successfully.',
            'assignment': assignment,
        }
    else:
        return {
            'success': True,
            'message': f'Package "{package.display_name}" assignment updated.',
            'assignment': assignment,
        }


def remove_package_assignment(
    *,
    remover: User,
    target_user: User,
    package_id: int,
) -> dict:
    """
    Remove a package assignment from target_user.

    Admin only.
    """
    from apps.fund_management.models import UserPackageAssignment

    remover_role = (getattr(remover, 'role', None) or '').strip()

    assignment = UserPackageAssignment.objects.filter(
        user=target_user,
        package_id=package_id,
        is_deleted=False,
    ).first()

    if not assignment:
        return {'success': False, 'message': 'Assignment not found.'}

    can_remove = is_platform_operator(remover_role)

    if not can_remove:
        return {
            'success': False,
            'message': 'You do not have permission to remove this assignment.',
        }

    assignment.is_deleted = True
    assignment.save(update_fields=['is_deleted', 'updated_at'])

    logger.info(
        'Package assignment removed: package=%s from user=%s by remover=%s',
        package_id,
        target_user.user_id,
        remover.user_id,
    )

    return {'success': True, 'message': 'Package assignment removed.'}


def auto_assign_default_package(user: User, assigner: User = None) -> dict:
    """
    Automatically assign the default package to a new user.
    Called during user creation.
    
    Returns dict with 'success', 'assignment', 'message'.
    """
    from apps.fund_management.models import UserPackageAssignment

    default_pkg = PayInPackage.objects.filter(
        is_default=True, is_active=True, is_deleted=False
    ).first()

    if not default_pkg:
        return {
            'success': False,
            'message': 'No default package configured.',
            'assignment': None,
        }

    assignment, created = UserPackageAssignment.objects.get_or_create(
        user=user,
        package=default_pkg,
        defaults={'assigned_by': assigner},
    )

    if created:
        logger.info(
            'Default package auto-assigned: package=%s (%s) to new user=%s',
            default_pkg.pk,
            default_pkg.display_name,
            user.user_id,
        )
        return {
            'success': True,
            'message': f'Default package "{default_pkg.display_name}" assigned.',
            'assignment': assignment,
        }
    else:
        return {
            'success': True,
            'message': 'User already has the default package.',
            'assignment': assignment,
        }


def get_assignable_packages_for_user(assigner: User):
    """
    Returns packages an Admin may assign to users (all active packages).
    Non-admin callers should not use assignment flows; returns empty queryset.
    """
    assigner_role = (getattr(assigner, 'role', None) or '').strip()
    if not is_platform_operator(assigner_role):
        return PayInPackage.objects.none()
    return PayInPackage.objects.filter(is_active=True, is_deleted=False).order_by('sort_order', 'display_name')
