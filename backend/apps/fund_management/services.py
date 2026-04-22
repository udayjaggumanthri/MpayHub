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

from apps.admin_panel.models import PaymentGateway, PayoutGateway
from apps.bank_accounts.models import BankAccount
from apps.contacts.models import Contact
from apps.authentication.models import User
from apps.core.exceptions import InsufficientBalance, TransactionFailed
from apps.core.utils import decrypt_secret_payload
from apps.core.utils import generate_service_id
from apps.fund_management.models import LoadMoney, PayInPackage, Payout, PayoutSlabTier
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


def quote_payin(package: PayInPackage, gross: Decimal, payer_user: Optional[User] = None) -> dict:
    """Build line-item breakdown; net = gross - sum(deduction slices). Pass payer_user for upline-aware admin absorption."""
    dist = _compute_payin_distribution(package, gross, payer_user)
    return {
        'snapshot': dist['snapshot'],
        'net_credit': dist['net_credit'],
        'total_deduction': dist['total_deduction'],
        'retailer_commission': dist['retailer_commission'],
        'retailer_share_absorbed_to_admin': dist['retailer_absorbed_to_admin'],
        'lines': dist['lines'],
    }


def _api_master_for_payin_razorpay(package: PayInPackage):
    """
    Resolve which ApiMaster supplies Razorpay keys for this pay-in package.

    1) Payment gateway's linked API Master (payments) — preferred for multi-provider setups.
    2) Else, first payments-type row with a Razorpay-like provider_code (is_default / priority order).
       This matches ops who configure credentials only in API Master without re-linking the gateway row.
    """
    from apps.integrations.models import ApiMaster
    from apps.integrations.razorpay_orders import is_razorpay_like_provider_code

    pg = getattr(package, 'payment_gateway', None)
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


def _razorpay_keypair_for_payin_package(package: PayInPackage):
    """Resolved Razorpay key_id + key_secret from API Master (live read); optional .env fallback if unset."""
    from apps.integrations.razorpay_orders import (
        extract_razorpay_key_pair_from_secrets,
        resolve_razorpay_credentials,
    )

    key_id = None
    key_secret = None
    api_master = _api_master_for_payin_razorpay(package)
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


def create_payin_order(user, *, package_id: int, gross: Decimal, contact_id: int):
    """Create pending LoadMoney; call Razorpay outside DB transaction when needed."""
    package = (
        PayInPackage.objects.filter(id=package_id, is_active=True, is_deleted=False)
        .select_related('payment_gateway', 'payment_gateway__api_master')
        .first()
    )
    if not package:
        raise ValueError('Invalid or inactive package')
    if package.provider == 'payu':
        raise TransactionFailed('PayU checkout is not enabled yet. Use a mock or Razorpay package.')

    contact = Contact.objects.filter(id=contact_id, user=user).first()
    if not contact:
        raise ValueError('Contact not found')

    q = quote_payin(package, gross, user)

    lm = None
    last_integrity: IntegrityError | None = None
    for attempt in range(2):
        tid = generate_service_id('load_money')
        try:
            with db_transaction.atomic():
                lm = LoadMoney.objects.create(
                    user=user,
                    package=package,
                    amount=money_q(gross),
                    gateway=str(package.code),
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
        'amount': str(lm.amount),
        'currency': 'INR',
        'customer_name': contact.name,
        'customer_email': contact.email,
        'customer_phone': contact.phone,
        'fee_preview': q['snapshot'],
    }

    if package.provider == 'razorpay':
        from apps.integrations.razorpay_orders import create_order as rz_order

        checkout_key_id, checkout_key_secret = _razorpay_keypair_for_payin_package(package)

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

    key_id, key_secret = _razorpay_keypair_for_payin_package(lm.package)
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

        return load_money
    except Exception as e:
        load_money.status = 'FAILED'
        load_money.failure_reason = str(e)
        load_money.save(update_fields=['status', 'failure_reason'])
        raise TransactionFailed(f'Load money failed: {str(e)}') from e


@db_transaction.atomic
def process_payout(user, bank_account_id, amount, gateway_id=None, transfer_mode: str = 'IMPS'):
    from apps.bank_accounts.models import BankAccount

    try:
        bank_account = BankAccount.objects.get(id=bank_account_id, user=user)
    except BankAccount.DoesNotExist:
        raise ValueError('Bank account not found') from None

    amount = money_q(Decimal(str(amount)))
    charge_amt = payout_slab_charge_for_user(user, amount)
    platform_fee = Decimal('0')
    total_deducted = money_q(amount + charge_amt)

    main_wallet = Wallet.get_wallet(user, 'main')
    if main_wallet.balance < total_deducted:
        raise InsufficientBalance(
            f'Insufficient balance. Available: ₹{main_wallet.balance}, Required: ₹{total_deducted}'
        )

    payout = None
    last_integrity: IntegrityError | None = None
    for attempt in range(2):
        tid = generate_service_id('payout')
        try:
            with db_transaction.atomic():
                payout = Payout.objects.create(
                    user=user,
                    bank_account=bank_account,
                    amount=amount,
                    charge=charge_amt,
                    platform_fee=platform_fee,
                    total_deducted=total_deducted,
                    transfer_mode=transfer_mode,
                    status='PENDING',
                    transaction_id=tid,
                )
            break
        except IntegrityError as exc:
            last_integrity = exc
            logger.warning('Payout create id collision (attempt %s)', attempt)
    if payout is None:
        raise TransactionFailed(
            'Could not allocate a unique payout reference; please retry.'
        ) from last_integrity

    try:
        gateway_transaction_id = f'PTX{payout.transaction_id}'
        payout.gateway_transaction_id = gateway_transaction_id
        payout.status = 'SUCCESS'
        payout.save(update_fields=['gateway_transaction_id', 'status'])

        opening_balance = main_wallet.balance
        main_wallet.debit(total_deducted, reference=payout.transaction_id)
        closing_balance = main_wallet.balance

        Transaction.objects.create(
            user=user,
            transaction_type='payout',
            amount=amount,
            charge=charge_amt,
            platform_fee=platform_fee,
            net_amount=total_deducted,
            status='SUCCESS',
            service_id=payout.transaction_id,
            reference=gateway_transaction_id,
            service_family='payout',
            bank_txn_id=gateway_transaction_id[:191],
            **transaction_agent_db_fields(user),
        )

        PassbookEntry.objects.create(
            user=user,
            wallet_type='main',
            service='PAYOUT',
            service_id=payout.transaction_id,
            description=(
                f'PAYOUT {transfer_mode}, A/C ..{bank_account.account_number[-4:]}, IFSC {bank_account.ifsc}, '
                f'AMOUNT ₹{amount}, CHARGE ₹{charge_amt}'
            ),
            debit_amount=total_deducted,
            credit_amount=Decimal('0'),
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            service_charge=charge_amt,
            principal_amount=amount,
            **passbook_initiator_db_fields(user),
        )

        logger.info(
            'payout completed',
            extra={
                'event': 'payout_success',
                'user_id': user.pk,
                'transaction_id': payout.transaction_id,
                'service_id': payout.transaction_id,
                'amount': str(amount),
                'status': payout.status,
            },
        )
        return payout
    except Exception as e:
        logger.info(
            'payout failed',
            extra={
                'event': 'payout_failure',
                'user_id': user.pk,
                'transaction_id': getattr(payout, 'transaction_id', ''),
                'service_id': getattr(payout, 'transaction_id', ''),
                'amount': str(amount),
                'status': 'FAILED',
            },
        )
        payout.status = 'FAILED'
        payout.failure_reason = str(e)
        payout.save(update_fields=['status', 'failure_reason'])
        raise TransactionFailed(f'Payout failed: {str(e)}') from e


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
    """
    from apps.fund_management.models import UserPackageAssignment

    # Admin users can access all packages
    user_role = (getattr(user, 'role', None) or '').strip()
    if user_role == 'Admin':
        return PayInPackage.objects.filter(is_active=True, is_deleted=False).order_by('sort_order', 'display_name')

    # Check explicit assignments
    assigned_pkg_ids = UserPackageAssignment.objects.filter(
        user=user, is_deleted=False
    ).values_list('package_id', flat=True)

    if assigned_pkg_ids:
        return PayInPackage.objects.filter(
            id__in=assigned_pkg_ids,
            is_active=True,
            is_deleted=False,
        ).order_by('sort_order', 'display_name')

    # Fallback to default package
    return PayInPackage.objects.filter(
        is_default=True,
        is_active=True,
        is_deleted=False,
    ).order_by('sort_order', 'display_name')


def resolve_payout_package(user: User) -> Optional[PayInPackage]:
    """
    Single PayInPackage used for payout slab lookup: first row from the same ordered set
    as pay-in access (sort_order, display_name).
    """
    qs = get_user_accessible_packages(user)
    return qs.first()


def payout_flat_charge_for_package(package: Optional[PayInPackage], amount: Decimal) -> Decimal:
    """
    Flat payout charge for amount using tiers on ``package``.
    If ``package`` is None or has no tiers, uses global PayoutSlabConfig / settings.
    """
    amount = money_q(Decimal(str(amount)))
    if package is None:
        return _payout_slab_charge_global(amount)
    tiers = (
        PayoutSlabTier.objects.filter(package=package, is_deleted=False)
        .only('min_amount', 'max_amount', 'flat_charge', 'sort_order')
        .order_by('sort_order', 'min_amount')
    )
    if not tiers.exists():
        return _payout_slab_charge_global(amount)
    for t in tiers:
        lo = money_q(t.min_amount)
        hi = money_q(t.max_amount) if t.max_amount is not None else None
        if amount < lo:
            continue
        if hi is not None and amount > hi:
            continue
        return money_q(t.flat_charge)
    return _payout_slab_charge_global(amount)


def payout_slab_charge_for_user(user: User, amount: Decimal) -> Decimal:
    """Payout flat charge for user's resolved commercial package (per-package tiers)."""
    pkg = resolve_payout_package(user)
    return payout_flat_charge_for_package(pkg, amount)


def max_payout_eligible_for_user(user: User, balance: Decimal) -> Decimal:
    """
    Maximum payout principal such that principal + charge(principal) <= balance,
    using tiers on the user's resolved package (or global two-tier fallback).
    """
    balance = money_q(Decimal(str(balance)))
    if balance <= 0:
        return Decimal('0')
    pkg = resolve_payout_package(user)
    if pkg is None:
        return _max_payout_eligible_global(balance)
    tiers = list(
        PayoutSlabTier.objects.filter(package=pkg, is_deleted=False).order_by('sort_order', 'min_amount')
    )
    if not tiers:
        return _max_payout_eligible_global(balance)
    best = Decimal('0')
    for t in tiers:
        c = money_q(t.flat_charge)
        lo = money_q(t.min_amount)
        hi = money_q(t.max_amount) if t.max_amount is not None else None
        cap = money_q(balance - c)
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
    Check if assigner has access to a package and can delegate it to others.
    Admin can assign any active package.
    Non-admin can only assign packages they have been assigned.
    """
    from apps.fund_management.models import UserPackageAssignment

    assigner_role = (getattr(assigner, 'role', None) or '').strip()
    
    # Admin can assign any active package
    if assigner_role == 'Admin':
        return PayInPackage.objects.filter(
            id=package_id, is_active=True, is_deleted=False
        ).exists()

    # Non-admin must have the package assigned to them
    return UserPackageAssignment.objects.filter(
        user=assigner,
        package_id=package_id,
        is_deleted=False,
    ).exists()


def is_user_in_downline(senior: User, junior: User) -> bool:
    """
    Check if junior is in senior's direct downline hierarchy.
    Uses the parent chain to verify.
    """
    if senior.pk == junior.pk:
        return False
    
    senior_role = (getattr(senior, 'role', None) or '').strip()
    if senior_role == 'Admin':
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
    Assign a package from assigner's pool to target_user.
    
    Validation:
    - Assigner must have access to the package (or be Admin)
    - Target must be in assigner's downline (or assigner is Admin)
    - Package must be active
    
    Returns dict with 'success', 'assignment', 'message'.
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
    if assigner_role != 'Admin' and not is_user_in_downline(assigner, target_user):
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
    
    Validation:
    - Remover must be Admin or the original assigner or an upline of target
    
    Returns dict with 'success', 'message'.
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

    # Permission check: Admin, original assigner, or upline can remove
    can_remove = (
        remover_role == 'Admin'
        or (assignment.assigned_by and assignment.assigned_by.pk == remover.pk)
        or is_user_in_downline(remover, target_user)
    )

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
    Returns packages that the assigner can assign to their downline.
    Admin: all active packages.
    Non-admin: only packages assigned to them.
    """
    assigner_role = (getattr(assigner, 'role', None) or '').strip()
    
    if assigner_role == 'Admin':
        return PayInPackage.objects.filter(
            is_active=True, is_deleted=False
        ).order_by('sort_order', 'display_name')

    return get_user_assigned_packages(assigner)
