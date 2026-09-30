"""
Payout domain orchestrator: hold → provider initiate → callback settle/release.

Never imports Vidual URLs or crypto; uses integrations.payout.registry only.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.db import IntegrityError
from django.db import transaction as db_transaction
from django.utils import timezone
from datetime import timedelta

from apps.core.maintenance_mode import MODULE_PAYOUT, assert_module_available
from apps.bank_accounts.models import BankAccount
from apps.core.exceptions import InsufficientBalance, TransactionFailed
from apps.core.utils import generate_service_id
from apps.fund_management.models import Payout, PayoutProviderEvent
from apps.fund_management.money_utils import money_q
from apps.integrations.payout.exceptions import (
    PayoutConfigurationError,
    PayoutInitiateError,
)
from apps.integrations.payout.beneficiary_location import resolve_beneficiary_location
from apps.integrations.payout.masters_cache import get_masters, match_bank_code
from apps.integrations.payout.registry import resolve_payout_provider
from apps.integrations.payout.types import (
    DOMAIN_FAILED,
    DOMAIN_PENDING,
    DOMAIN_SUCCESS,
    PayoutCallbackEvent,
    PayoutInitiateRequest,
)
from apps.transactions.agent_snapshot import (
    passbook_initiator_db_fields,
    transaction_agent_db_fields,
)
from apps.transactions.models import PassbookEntry, Transaction
from apps.wallets.models import Wallet

logger = logging.getLogger(__name__)

# Fallback limits only if provider.amount_limits() cannot be read
_DEFAULT_MIN_AMOUNT = Decimal('100')
_DEFAULT_MAX_AMOUNT = Decimal('100000')


def _mask_account(acct: str) -> str:
    a = str(acct or '')
    if len(a) >= 4:
        return f'XXXX{a[-4:]}'
    return a or 'XXXX'


def _log_event(
    *,
    payout: Payout | None,
    provider_code: str,
    direction: str,
    event_type: str,
    merchant_ref_id: str = '',
    http_status: int | None = None,
    payload: dict | None = None,
    notes: str = '',
) -> None:
    try:
        PayoutProviderEvent.objects.create(
            payout=payout,
            provider_code=provider_code or '',
            direction=direction,
            event_type=event_type,
            merchant_ref_id=merchant_ref_id or (payout.merchant_ref_id if payout else ''),
            http_status=http_status,
            payload=payload or {},
            notes=notes or '',
        )
    except Exception:
        logger.exception('Failed to write PayoutProviderEvent')


def _provider_limits(provider) -> tuple[Decimal, Decimal]:
    try:
        return provider.amount_limits()
    except Exception:
        return _DEFAULT_MIN_AMOUNT, _DEFAULT_MAX_AMOUNT


def _default_purpose(provider) -> str:
    try:
        return provider.default_purpose_code()
    except Exception:
        return '004'


def process_payout(
    user,
    bank_account_id,
    amount,
    gateway_id=None,
    transfer_mode: str = 'IMPS',
    *,
    beneficiary_location: str = '',
    purpose_code: str = '',
    lat: str = '',
    long: str = '',
    udf1: str = '',
    udf2: str = '',
    udf3: str = '',
):
    """
    Initiate a real provider payout:
      1. Validate + create PENDING Payout
      2. Hold amount + slab charge
      3. Call provider (outside hold txn success path)
      4. Stay PENDING until callback; never fake SUCCESS
    """
    # Defense in depth: views also call assert_module_available; keep orchestrator closed
    # if invoked from any other code path during maintenance.
    assert_module_available(MODULE_PAYOUT)

    del gateway_id  # routing is via ApiMaster registry; optional UI gateway is display-only

    try:
        bank_account = BankAccount.objects.get(id=bank_account_id, user=user)
    except BankAccount.DoesNotExist:
        raise ValueError('Bank account not found') from None

    amount = money_q(Decimal(str(amount)))
    mode = (transfer_mode or 'IMPS').strip().upper()

    # Double-submit guard: same user + bank + amount + mode within 90s returns existing row
    # instead of creating a second hold / second provider payout.
    recent = (
        Payout.objects.filter(
            user=user,
            bank_account_id=bank_account_id,
            amount=amount,
            transfer_mode=mode,
            status__in=('PENDING', 'SUCCESS'),
            created_at__gte=timezone.now() - timedelta(seconds=90),
            is_deleted=False,
        )
        .order_by('-created_at')
        .first()
    )
    if recent is not None:
        logger.warning(
            'payout duplicate suppressed',
            extra={
                'event': 'payout_duplicate_suppressed',
                'user_id': user.pk,
                'existing_transaction_id': recent.transaction_id,
                'amount': str(amount),
            },
        )
        return recent

    try:
        provider = resolve_payout_provider()
    except PayoutConfigurationError as exc:
        raise TransactionFailed(str(exc)) from exc

    allowed_modes = provider.supported_transfer_modes()
    if not allowed_modes:
        allowed_modes = frozenset({'IMPS', 'NEFT'})
    if mode not in allowed_modes:
        raise ValueError(
            f'Transfer mode must be one of {", ".join(sorted(allowed_modes))} for the active payout provider.'
        )
    min_amt, max_amt = _provider_limits(provider)
    if amount < min_amt:
        raise ValueError(f'Minimum payout amount is ₹{min_amt}.')
    if amount > max_amt:
        raise ValueError(f'Maximum payout amount is ₹{max_amt}.')

    purpose = (purpose_code or '').strip() or _default_purpose(provider)

    banks = get_masters(provider, 'banks')
    bank_code = match_bank_code(
        banks,
        bank_name=bank_account.bank_name or '',
        ifsc=bank_account.ifsc or '',
    )
    if not bank_code:
        raise ValueError(
            f'Could not map bank "{bank_account.bank_name}" / IFSC {bank_account.ifsc} '
            'to a payout provider bank code. Please contact support or re-verify the account.'
        )

    # Auto-resolve beneficiary state from bank account IFSC / verification metadata.
    # Client-provided location remains an optional fallback for older clients.
    states = get_masters(provider, 'states')
    location = resolve_beneficiary_location(
        bank_account=bank_account,
        states=states,
        preferred=(beneficiary_location or '').strip(),
    )
    if not location:
        raise ValueError(
            'Could not determine beneficiary state from the selected bank account IFSC. '
            'Please re-verify the account or contact support.'
        )

    from apps.fund_management.services import payout_slab_charge_for_user

    charge_amt = payout_slab_charge_for_user(user, amount)
    platform_fee = Decimal('0')
    total_deducted = money_q(amount + charge_amt)

    main_wallet = Wallet.get_wallet(user, 'main')
    available = money_q(
        Decimal(str(main_wallet.balance or 0)) - Decimal(str(main_wallet.held_balance or 0))
    )
    if available < total_deducted:
        raise InsufficientBalance(
            f'Insufficient available balance. Available: ₹{available}, Required: ₹{total_deducted}'
        )

    mobile = (
        str(getattr(bank_account, 'mobile_number', '') or '').strip()
        or str(getattr(user, 'phone', '') or '').strip()
    )
    if len(mobile) == 12 and mobile.startswith('91'):
        mobile = mobile[2:]
    if len(mobile) != 10 or not mobile.isdigit():
        raise ValueError('A valid 10-digit beneficiary mobile number is required for payout.')

    beneficiary_name = (
        (bank_account.beneficiary_name or bank_account.account_holder_name or '').strip()
    )
    if not beneficiary_name:
        raise ValueError('Beneficiary name is required on the bank account.')
    # Provider-specific normalization (e.g. VimoPay alphabet-only) before hold
    clean_name = provider.normalize_beneficiary_name(beneficiary_name)
    if len(clean_name) < 2:
        raise ValueError(
            'Beneficiary name must contain only letters and spaces (at least 2 characters). '
            f'Current name "{beneficiary_name}" is not accepted by the payout provider.'
        )
    beneficiary_name = clean_name

    lat_s = str(lat or '').strip() or '28.7041'
    long_s = str(long or '').strip() or '77.1025'

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
                    transfer_mode=mode,
                    status='PENDING',
                    transaction_id=tid,
                    merchant_ref_id=tid,
                    provider_code=provider.provider_code,
                    purpose_code=purpose,
                    beneficiary_location=location,
                    request_meta={
                        'bank_code': bank_code,
                        'account_masked': _mask_account(bank_account.account_number),
                        'ifsc': bank_account.ifsc,
                        'lat': lat_s,
                        'long': long_s,
                    },
                )
                main_wallet.hold(
                    total_deducted,
                    reference=tid,
                    description=f'Payout hold {tid}',
                )
            break
        except IntegrityError as exc:
            last_integrity = exc
            logger.warning('Payout create id collision (attempt %s)', attempt)
    if payout is None:
        raise TransactionFailed(
            'Could not allocate a unique payout reference; please retry.'
        ) from last_integrity

    _notify_pending(user, payout, amount)

    initiate_req = PayoutInitiateRequest(
        merchant_ref_id=payout.transaction_id,
        amount=amount,
        payment_mode=mode,
        beneficiary_account_number=str(bank_account.account_number),
        beneficiary_ifsc=str(bank_account.ifsc).upper(),
        beneficiary_name=beneficiary_name,
        beneficiary_mobile=mobile,
        beneficiary_bank_code=bank_code,
        beneficiary_location=location,
        payment_purpose=purpose,
        lat=lat_s,
        long=long_s,
        udf1=udf1 or str(user.pk),
        udf2=udf2 or '',
        udf3=udf3 or '',
    )

    try:
        result = provider.initiate(initiate_req)
    except PayoutInitiateError as exc:
        _fail_and_release(
            payout,
            reason=str(exc),
            provider_code=provider.provider_code,
            status_code=getattr(exc, 'code', '') or '',
            details=getattr(exc, 'details', None),
        )
        raise TransactionFailed(f'Payout failed: {exc}') from exc
    except Exception as exc:
        logger.exception('Payout provider initiate unexpected error')
        _fail_and_release(
            payout,
            reason=str(exc)[:500],
            provider_code=provider.provider_code,
        )
        raise TransactionFailed(f'Payout failed: {exc}') from exc

    # Provider accepted (usually Queued) — stay PENDING with hold
    with db_transaction.atomic():
        locked = Payout.objects.select_for_update().get(pk=payout.pk)
        locked.provider_txn_id = result.provider_txn_id or ''
        locked.gateway_transaction_id = result.provider_txn_id or locked.gateway_transaction_id
        locked.provider_status_code = result.provider_status_code or ''
        locked.response_meta = {
            'initiate': {
                'domain_status': result.domain_status,
                'provider_status_code': result.provider_status_code,
                'response_message': result.response_message,
                'charges': str(result.charges) if result.charges is not None else None,
            }
        }
        if result.charges is not None:
            locked.provider_charges = money_q(result.charges)
        if result.domain_status == DOMAIN_FAILED:
            # Should have raised; defensive
            pass
        elif result.domain_status == DOMAIN_SUCCESS:
            # Extremely rare for VimoPay (usually queued). Settle immediately.
            locked.save(
                update_fields=[
                    'provider_txn_id',
                    'gateway_transaction_id',
                    'provider_status_code',
                    'response_meta',
                    'provider_charges',
                ]
            )
            _settle_success(
                locked,
                rrn='',
                provider_txn_id=result.provider_txn_id,
                status_code=result.provider_status_code,
                response_message=result.response_message,
                provider_charges=result.charges,
            )
            payout.refresh_from_db()
            return payout
        locked.status = 'PENDING'
        locked.save(
            update_fields=[
                'provider_txn_id',
                'gateway_transaction_id',
                'provider_status_code',
                'response_meta',
                'provider_charges',
                'status',
            ]
        )

    _log_event(
        payout=payout,
        provider_code=provider.provider_code,
        direction='outbound',
        event_type='initiate',
        merchant_ref_id=payout.transaction_id,
        payload={
            'domain_status': result.domain_status,
            'provider_status_code': result.provider_status_code,
            'provider_txn_id': result.provider_txn_id,
            'response_message': result.response_message,
        },
    )

    logger.info(
        'payout queued with provider',
        extra={
            'event': 'payout_queued',
            'user_id': user.pk,
            'transaction_id': payout.transaction_id,
            'provider_txn_id': result.provider_txn_id,
            'provider_status_code': result.provider_status_code,
        },
    )
    payout.refresh_from_db()
    return payout


def _fail_and_release(
    payout: Payout,
    *,
    reason: str,
    provider_code: str = '',
    status_code: str = '',
    details: Any = None,
) -> None:
    with db_transaction.atomic():
        locked = Payout.objects.select_for_update().get(pk=payout.pk)
        if locked.status in ('SUCCESS', 'FAILED'):
            return
        wallet = Wallet.get_wallet(locked.user, 'main')
        try:
            wallet.release(
                locked.total_deducted,
                reference=locked.transaction_id,
                description=f'Payout release {locked.transaction_id}',
            )
        except Exception:
            logger.exception('Payout release failed for %s', locked.transaction_id)
        locked.status = 'FAILED'
        locked.failure_reason = (reason or '')[:2000]
        locked.provider_status_code = status_code or locked.provider_status_code
        if details:
            meta = locked.response_meta if isinstance(locked.response_meta, dict) else {}
            meta['failure'] = details if isinstance(details, dict) else {'detail': str(details)}
            locked.response_meta = meta
        locked.save(
            update_fields=['status', 'failure_reason', 'provider_status_code', 'response_meta']
        )
    _log_event(
        payout=payout,
        provider_code=provider_code or payout.provider_code,
        direction='outbound',
        event_type='initiate_failed',
        merchant_ref_id=payout.transaction_id,
        payload={'reason': reason, 'code': status_code},
        notes=reason,
    )
    _notify_failed(payout.user, payout, reason)


def apply_payout_callback(event: PayoutCallbackEvent, *, provider_code: str = '') -> Payout | None:
    """
    Idempotent callback handler. Returns the Payout row or None if unknown ref.
    """
    ref = (event.merchant_ref_id or '').strip()
    if not ref:
        logger.warning('Payout callback missing merchantRefId')
        return None

    with db_transaction.atomic():
        payout = (
            Payout.objects.select_for_update()
            .filter(merchant_ref_id=ref)
            .first()
        )
        if payout is None:
            payout = (
                Payout.objects.select_for_update()
                .filter(transaction_id=ref)
                .first()
            )
        if payout is None:
            logger.warning('Payout callback for unknown merchantRefId=%s', ref)
            _log_event(
                payout=None,
                provider_code=provider_code,
                direction='inbound',
                event_type='callback_unknown_ref',
                merchant_ref_id=ref,
                payload=event.raw if isinstance(event.raw, dict) else {'raw': str(event.raw)},
            )
            return None

        _log_event(
            payout=payout,
            provider_code=provider_code or payout.provider_code,
            direction='inbound',
            event_type='callback',
            merchant_ref_id=ref,
            payload={
                'domain_status': event.domain_status,
                'provider_status_code': event.provider_status_code,
                'rrn': event.rrn,
                'provider_txn_id': event.provider_txn_id,
                'response_message': event.response_message,
            },
        )

        if payout.status in ('SUCCESS', 'FAILED'):
            # Idempotent ACK — do not touch wallet again
            return payout

        payout.callback_received_at = timezone.now()
        payout.provider_status_code = event.provider_status_code or payout.provider_status_code
        if event.provider_txn_id:
            payout.provider_txn_id = event.provider_txn_id
            payout.gateway_transaction_id = event.provider_txn_id
        if event.rrn:
            payout.rrn = event.rrn
        if event.charges is not None:
            payout.provider_charges = money_q(event.charges)
        meta = payout.response_meta if isinstance(payout.response_meta, dict) else {}
        meta['callback'] = event.raw if isinstance(event.raw, dict) else {'raw': str(event.raw)}
        payout.response_meta = meta

        if event.domain_status == DOMAIN_PENDING:
            payout.save(
                update_fields=[
                    'callback_received_at',
                    'provider_status_code',
                    'provider_txn_id',
                    'gateway_transaction_id',
                    'rrn',
                    'provider_charges',
                    'response_meta',
                ]
            )
            return payout

        if event.domain_status == DOMAIN_FAILED:
            wallet = Wallet.get_wallet(payout.user, 'main')
            try:
                wallet.release(
                    payout.total_deducted,
                    reference=payout.transaction_id,
                    description=f'Payout release {payout.transaction_id}',
                )
            except Exception:
                logger.exception('Callback release failed for %s', payout.transaction_id)
            payout.status = 'FAILED'
            payout.failure_reason = (event.response_message or 'Payout failed at provider')[:2000]
            payout.save(
                update_fields=[
                    'status',
                    'failure_reason',
                    'callback_received_at',
                    'provider_status_code',
                    'provider_txn_id',
                    'gateway_transaction_id',
                    'rrn',
                    'provider_charges',
                    'response_meta',
                ]
            )
            _notify_failed(payout.user, payout, payout.failure_reason)
            return payout

        # SUCCESS
        payout.save(
            update_fields=[
                'callback_received_at',
                'provider_status_code',
                'provider_txn_id',
                'gateway_transaction_id',
                'rrn',
                'provider_charges',
                'response_meta',
            ]
        )
        _settle_success(
            payout,
            rrn=event.rrn or '',
            provider_txn_id=event.provider_txn_id or payout.provider_txn_id,
            status_code=event.provider_status_code,
            response_message=event.response_message,
            provider_charges=event.charges,
        )
        return payout


def _settle_success(
    payout: Payout,
    *,
    rrn: str,
    provider_txn_id: str,
    status_code: str,
    response_message: str,
    provider_charges: Decimal | None,
) -> None:
    """Convert hold → debit and write ledger. Caller should hold select_for_update when possible."""
    locked = Payout.objects.select_for_update().get(pk=payout.pk)
    if locked.status == 'SUCCESS':
        return
    if locked.status == 'FAILED':
        logger.error('Cannot settle FAILED payout %s', locked.transaction_id)
        return

    wallet = Wallet.get_wallet(locked.user, 'main')
    opening_balance = wallet.balance
    wallet.settle_hold(
        locked.total_deducted,
        reference=locked.transaction_id,
        description=f'Payout settle {locked.transaction_id}',
    )
    closing_balance = wallet.balance

    utr = (rrn or provider_txn_id or locked.gateway_transaction_id or locked.transaction_id)[:191]
    locked.status = 'SUCCESS'
    locked.rrn = rrn or locked.rrn
    locked.provider_txn_id = provider_txn_id or locked.provider_txn_id
    locked.gateway_transaction_id = provider_txn_id or locked.gateway_transaction_id or utr
    locked.provider_status_code = status_code or locked.provider_status_code or '000'
    if provider_charges is not None:
        locked.provider_charges = money_q(provider_charges)
    if response_message:
        meta = locked.response_meta if isinstance(locked.response_meta, dict) else {}
        meta['success_message'] = response_message
        locked.response_meta = meta
    locked.save(
        update_fields=[
            'status',
            'rrn',
            'provider_txn_id',
            'gateway_transaction_id',
            'provider_status_code',
            'provider_charges',
            'response_meta',
        ]
    )

    bank_account = locked.bank_account
    Transaction.objects.create(
        user=locked.user,
        transaction_type='payout',
        amount=locked.amount,
        charge=locked.charge,
        platform_fee=locked.platform_fee,
        net_amount=locked.total_deducted,
        status='SUCCESS',
        service_id=locked.transaction_id,
        reference=utr,
        service_family='payout',
        bank_txn_id=utr[:191],
        **transaction_agent_db_fields(locked.user),
    )

    PassbookEntry.objects.create(
        user=locked.user,
        wallet_type='main',
        service='PAYOUT',
        service_id=locked.transaction_id,
        description=(
            f'PAYOUT {locked.transfer_mode}, A/C ..{str(bank_account.account_number)[-4:]}, '
            f'IFSC {bank_account.ifsc}, AMOUNT ₹{locked.amount}, CHARGE ₹{locked.charge}'
            + (f', UTR {rrn}' if rrn else '')
        ),
        debit_amount=locked.total_deducted,
        credit_amount=Decimal('0'),
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        service_charge=locked.charge,
        principal_amount=locked.amount,
        **passbook_initiator_db_fields(locked.user),
    )

    if locked.charge > 0:
        try:
            from apps.transactions.services.fee_settlement import settle_service_charge

            settle_service_charge(
                payer=locked.user,
                module='payout',
                service_id=locked.transaction_id,
                charge=locked.charge,
                principal=locked.amount,
                meta={'transfer_mode': locked.transfer_mode, 'rrn': rrn},
            )
        except Exception:
            logger.exception('Payout fee settlement failed for %s', locked.transaction_id)

    logger.info(
        'payout settled',
        extra={
            'event': 'payout_success',
            'user_id': locked.user_id,
            'transaction_id': locked.transaction_id,
            'rrn': rrn,
            'status': 'SUCCESS',
        },
    )
    _notify_success(locked.user, locked, utr)


def _notify_pending(user, payout, amount) -> None:
    try:
        from apps.notifications.services.dispatch import SmsNotificationService
        from apps.notifications.email_helpers import dispatch_user_email

        pending_ctx = {
            'amount': str(amount),
            'transaction_id': payout.transaction_id,
            'reference': payout.transaction_id,
        }
        SmsNotificationService.dispatch(
            'payout.pending',
            user.phone,
            pending_ctx,
            user_id=user.pk,
            idempotency_key=f'payout:{payout.transaction_id}:PENDING',
        )
        dispatch_user_email(
            'payout.pending',
            user,
            pending_ctx,
            idempotency_key=f'payout:{payout.transaction_id}:PENDING',
        )
    except Exception:
        pass


def _notify_success(user, payout, utr: str) -> None:
    try:
        from apps.notifications.services.dispatch import SmsNotificationService
        from apps.notifications.email_helpers import dispatch_user_email

        acct = str(getattr(payout.bank_account, 'account_number', '') or '')
        ctx = {
            'amount': str(payout.amount),
            'account': _mask_account(acct),
            'utr': utr,
            'reference': utr,
            'transfer_mode': payout.transfer_mode,
            'transaction_id': payout.transaction_id,
        }
        SmsNotificationService.dispatch(
            'payout.success',
            user.phone,
            ctx,
            user_id=user.pk,
            idempotency_key=f'payout:{payout.transaction_id}:SUCCESS',
        )
        dispatch_user_email(
            'payout.success',
            user,
            ctx,
            idempotency_key=f'payout:{payout.transaction_id}:SUCCESS',
        )
    except Exception:
        pass


def _notify_failed(user, payout, reason: str) -> None:
    try:
        from apps.notifications.services.dispatch import SmsNotificationService
        from apps.notifications.email_helpers import dispatch_user_email

        acct = str(getattr(payout.bank_account, 'account_number', '') or '')
        txn_id = getattr(payout, 'transaction_id', '') or ''
        ctx = {
            'amount': str(payout.amount),
            'account': _mask_account(acct),
            'transaction_id': txn_id,
            'reference': txn_id,
            'reason': str(reason)[:200],
        }
        SmsNotificationService.dispatch(
            'payout.failed',
            user.phone,
            ctx,
            user_id=user.pk,
            idempotency_key=f'payout:{txn_id}:FAILED',
        )
        dispatch_user_email(
            'payout.failed',
            user,
            ctx,
            idempotency_key=f'payout:{txn_id}:FAILED',
        )
    except Exception:
        pass
