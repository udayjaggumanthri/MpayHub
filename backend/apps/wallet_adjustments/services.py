"""
Atomic admin wallet adjustment service.

Posts through existing Wallet.credit/debit + PassbookEntry so the user's
passbook stays consistent, and writes a dedicated WalletAdjustment audit row.
"""
from __future__ import annotations

import secrets
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.authentication.models import User
from apps.core.exceptions import InsufficientBalance
from apps.fund_management.money_utils import money_q
from apps.transactions.agent_snapshot import (
    display_name_for_user,
    passbook_initiator_db_fields,
)
from apps.transactions.models import PassbookEntry
from apps.wallets.models import Wallet
from apps.wallet_adjustments.exceptions import WalletAdjustmentError
from apps.wallet_adjustments.models import WalletAdjustment

ALLOWED_WALLET_TYPES = frozenset({'main', 'bbps'})
ALLOWED_ADJUSTMENT_TYPES = frozenset({'CREDIT', 'DEBIT'})
REASON_LABELS = dict(WalletAdjustment.REASON_CATEGORY_CHOICES)


def _generate_adjustment_id() -> str:
    stamp = timezone.now().strftime('%Y%m%d')
    suffix = secrets.token_hex(3).upper()
    return f'ADJ-{stamp}-{suffix}'


def _max_amount() -> Decimal:
    raw = getattr(settings, 'WALLET_ADJUSTMENT_MAX_AMOUNT', 100000)
    try:
        return money_q(Decimal(str(raw)))
    except (InvalidOperation, TypeError, ValueError):
        return money_q(Decimal('100000'))


def _admin_display_name(admin_user: User) -> str:
    try:
        return display_name_for_user(admin_user)[:255]
    except Exception:
        return (
            (admin_user.get_full_name() or '')
            or getattr(admin_user, 'user_id', '')
            or getattr(admin_user, 'phone', '')
            or str(admin_user.pk)
        )[:255]


def serialize_adjustment(adj: WalletAdjustment) -> dict:
    """JSON-friendly representation for API responses and exports."""
    user = adj.user
    return {
        'id': adj.id,
        'adjustment_id': adj.adjustment_id,
        'user': {
            'id': user.id if user else None,
            'user_id': getattr(user, 'user_id', None) or '',
            'display_code': getattr(user, 'display_code', None) or '',
            'phone': getattr(user, 'phone', None) or '',
            'name': display_name_for_user(user) if user else '',
            'role': getattr(user, 'role', None) or '',
        },
        'wallet_type': adj.wallet_type,
        'adjustment_type': adj.adjustment_type,
        'amount': str(money_q(adj.amount)),
        'reference_number': adj.reference_number,
        'reason_category': adj.reason_category,
        'reason_category_label': REASON_LABELS.get(adj.reason_category, adj.reason_category),
        'remarks': adj.remarks,
        'balance_before': str(money_q(adj.balance_before)),
        'balance_after': str(money_q(adj.balance_after)),
        'passbook_entry_id': adj.passbook_entry_id,
        'wallet_transaction_id': adj.wallet_transaction_id,
        'adjusted_by': {
            'id': adj.adjusted_by_id,
            'name': adj.adjusted_by_name
            or (display_name_for_user(adj.adjusted_by) if adj.adjusted_by else ''),
            'user_id': getattr(adj.adjusted_by, 'user_id', None) or '',
        },
        'status': adj.status,
        'failure_reason': adj.failure_reason or '',
        'created_at': adj.created_at.isoformat() if adj.created_at else None,
    }


def filter_adjustments(
    *,
    q: str = '',
    wallet_type: str = '',
    adjustment_type: str = '',
    date_from=None,
    date_to=None,
    status: str = '',
    reference: str = '',
    user_id: Optional[int] = None,
):
    qs = (
        WalletAdjustment.objects.filter(is_deleted=False)
        .select_related('user', 'adjusted_by', 'passbook_entry', 'wallet_transaction')
        .order_by('-created_at')
    )
    q = (q or '').strip()
    if q:
        qs = qs.filter(
            Q(user__phone__icontains=q)
            | Q(user__email__icontains=q)
            | Q(user__display_code__icontains=q)
            | Q(user__member_id__icontains=q)
            | Q(user__user_id__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(adjustment_id__icontains=q)
            | Q(reference_number__icontains=q)
        )
    if wallet_type:
        qs = qs.filter(wallet_type=wallet_type.strip().lower())
    if adjustment_type:
        qs = qs.filter(adjustment_type=adjustment_type.strip().upper())
    if status:
        qs = qs.filter(status=status.strip().upper())
    if reference:
        qs = qs.filter(reference_number__icontains=reference.strip())
    if user_id:
        qs = qs.filter(user_id=user_id)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs


@transaction.atomic
def apply_wallet_adjustment(
    *,
    admin_user: User,
    target_user: User,
    wallet_type: str,
    adjustment_type: str,
    amount,
    reference_number: str,
    reason_category: str,
    remarks: str,
) -> WalletAdjustment:
    """
    Validate, lock wallet, move funds, write passbook + audit row.

    Raises WalletAdjustmentError on validation failure, InsufficientBalance on debit shortfall.
    """
    wallet_type = str(wallet_type or '').strip().lower()
    adjustment_type = str(adjustment_type or '').strip().upper()
    reference_number = str(reference_number or '').strip()
    reason_category = str(reason_category or '').strip()
    remarks = str(remarks or '').strip()

    allowed = set(getattr(settings, 'WALLET_ADJUSTMENT_ALLOWED_TYPES', None) or ALLOWED_WALLET_TYPES)
    if wallet_type not in allowed:
        raise WalletAdjustmentError(
            f'Wallet type must be one of: {", ".join(sorted(allowed))}.',
            code='INVALID_WALLET_TYPE',
        )
    if adjustment_type not in ALLOWED_ADJUSTMENT_TYPES:
        raise WalletAdjustmentError(
            'Adjustment type must be CREDIT or DEBIT.',
            code='INVALID_ADJUSTMENT_TYPE',
        )
    if not reference_number:
        raise WalletAdjustmentError(
            'Transaction reference number is required.',
            code='REFERENCE_REQUIRED',
        )
    if len(reference_number) > 100:
        raise WalletAdjustmentError(
            'Reference number must be 100 characters or fewer.',
            code='REFERENCE_TOO_LONG',
        )
    if reason_category not in dict(WalletAdjustment.REASON_CATEGORY_CHOICES):
        raise WalletAdjustmentError(
            'A valid reason category is required.',
            code='REASON_REQUIRED',
        )
    if not remarks or len(remarks) < 5:
        raise WalletAdjustmentError(
            'Remarks are required (at least 5 characters).',
            code='REMARKS_REQUIRED',
        )
    if len(remarks) > 2000:
        raise WalletAdjustmentError(
            'Remarks must be 2000 characters or fewer.',
            code='REMARKS_TOO_LONG',
        )

    try:
        amount = money_q(Decimal(str(amount)))
    except (InvalidOperation, TypeError, ValueError):
        raise WalletAdjustmentError('Amount must be a valid number.', code='INVALID_AMOUNT')

    if amount <= 0:
        raise WalletAdjustmentError('Amount must be greater than zero.', code='INVALID_AMOUNT')

    max_amt = _max_amount()
    if amount > max_amt:
        raise WalletAdjustmentError(
            f'Amount exceeds the maximum allowed adjustment of ₹{max_amt}.',
            code='AMOUNT_CAP_EXCEEDED',
        )

    if not target_user or not getattr(target_user, 'pk', None):
        raise WalletAdjustmentError('Target user not found.', code='USER_NOT_FOUND')

    # Prevent accidental double-posting of the same correction.
    dup = (
        WalletAdjustment.objects.filter(
            user=target_user,
            reference_number=reference_number,
            adjustment_type=adjustment_type,
            status='SUCCESS',
            is_deleted=False,
        )
        .exists()
    )
    if dup:
        raise WalletAdjustmentError(
            'A successful adjustment already exists for this user, reference, and type. '
            'Use a different reference if this is a new correction.',
            code='DUPLICATE_REFERENCE',
        )

    # Ensure wallet exists, then lock for the duration of the adjustment.
    Wallet.get_wallet(target_user, wallet_type)
    wallet = (
        Wallet.objects.select_for_update()
        .filter(user=target_user, wallet_type=wallet_type, is_deleted=False)
        .first()
    )
    if not wallet:
        raise WalletAdjustmentError('Wallet could not be locked.', code='WALLET_LOCK_FAILED')

    balance_before = money_q(wallet.balance)
    reason_label = REASON_LABELS.get(reason_category, reason_category)
    description = f'Admin adjustment – {reason_label}: {remarks[:200]}'

    adjustment_id = _generate_adjustment_id()
    # Extremely unlikely collision; regenerate once.
    if WalletAdjustment.objects.filter(adjustment_id=adjustment_id).exists():
        adjustment_id = _generate_adjustment_id()

    try:
        if adjustment_type == 'CREDIT':
            wallet_txn = wallet.credit(
                amount,
                reference=adjustment_id,
                description=description,
            )
            debit_amount = Decimal('0')
            credit_amount = amount
        else:
            if balance_before < amount:
                raise InsufficientBalance(
                    f'Insufficient balance in {wallet_type} wallet. '
                    f'Available: ₹{balance_before}, Required: ₹{amount}'
                )
            wallet_txn = wallet.debit(
                amount,
                reference=adjustment_id,
                description=description,
            )
            debit_amount = amount
            credit_amount = Decimal('0')
    except InsufficientBalance:
        raise
    except ValueError as exc:
        raise WalletAdjustmentError(str(exc) or 'Wallet update failed.', code='WALLET_UPDATE_FAILED')

    wallet.refresh_from_db()
    balance_after = money_q(wallet.balance)

    passbook = PassbookEntry.objects.create(
        user=target_user,
        wallet_type=wallet_type,
        service='wallet_adjustment',
        service_id=adjustment_id,
        description=description,
        debit_amount=debit_amount,
        credit_amount=credit_amount,
        opening_balance=balance_before,
        closing_balance=balance_after,
        service_charge=Decimal('0'),
        principal_amount=amount,
        **passbook_initiator_db_fields(admin_user),
    )

    adj = WalletAdjustment.objects.create(
        adjustment_id=adjustment_id,
        user=target_user,
        wallet_type=wallet_type,
        adjustment_type=adjustment_type,
        amount=amount,
        reference_number=reference_number,
        reason_category=reason_category,
        remarks=remarks,
        balance_before=balance_before,
        balance_after=balance_after,
        passbook_entry=passbook,
        wallet_transaction=wallet_txn,
        adjusted_by=admin_user,
        adjusted_by_name=_admin_display_name(admin_user),
        status='SUCCESS',
    )
    return adj
