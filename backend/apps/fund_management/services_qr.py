"""Manual QR pay-in submit and validation."""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import IntegrityError, transaction as db_transaction
from rest_framework.exceptions import ValidationError

from apps.contacts.models import Contact
from apps.core.exceptions import TransactionFailed
from apps.core.utils import generate_service_id
from apps.fund_management.models import LoadMoney, PayInPackage, PayInQrAccount
from apps.fund_management.money_utils import money_q
from apps.fund_management.image_compression import compress_image_upload
from apps.fund_management.package_qr_accounts import resolve_qr_account_for_package
from apps.fund_management.qr_limits import assert_qr_can_accept
from apps.fund_management.services import get_user_accessible_packages, quote_payin

logger = logging.getLogger(__name__)

MAX_RECEIPT_BYTES = 5 * 1024 * 1024
ALLOWED_RECEIPT_TYPES = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp'}


def normalize_utr(raw: str) -> str:
    return ''.join(str(raw or '').split()).upper()[:64]


def utr_exists(utr: str) -> bool:
    if not utr:
        return False
    return LoadMoney.objects.filter(utr=utr, is_deleted=False).exists()


def validate_receipt_file(uploaded_file) -> None:
    if not uploaded_file:
        raise ValidationError({'receipt': 'Receipt screenshot is required.'})
    size = getattr(uploaded_file, 'size', 0) or 0
    if size > MAX_RECEIPT_BYTES:
        raise ValidationError({'receipt': 'Receipt must be 5MB or smaller.'})
    content_type = (getattr(uploaded_file, 'content_type', '') or '').lower()
    if content_type and content_type not in ALLOWED_RECEIPT_TYPES:
        raise ValidationError({'receipt': 'Receipt must be JPEG, PNG, or WebP.'})


@db_transaction.atomic
def submit_qr_payin(
    *,
    user,
    package_id: int,
    qr_account_id: int,
    contact_id: int,
    amount: Decimal,
    utr: str,
    payment_date,
    receipt_file,
) -> LoadMoney:
    utr_norm = normalize_utr(utr)
    if not utr_norm:
        raise ValidationError({'utr': 'UTR / reference number is required.'})
    if utr_exists(utr_norm):
        raise ValidationError(
            {'utr': 'This UTR already exists. Please verify and resubmit.'}
        )

    validate_receipt_file(receipt_file)
    receipt_file = compress_image_upload(receipt_file)

    package = PayInPackage.objects.filter(id=package_id, is_active=True, is_deleted=False).first()
    if not package:
        raise ValidationError({'package_id': 'Invalid or inactive package.'})
    if not get_user_accessible_packages(user).filter(pk=package.pk).exists():
        raise ValidationError({'package_id': 'Package not available for your account.'})

    qr = resolve_qr_account_for_package(package, qr_account_id)
    gross = money_q(amount)
    # Row lock prevents concurrent submits from exceeding the 24h daily limit.
    locked_qr = PayInQrAccount.objects.select_for_update().get(pk=qr.pk)
    try:
        assert_qr_can_accept(locked_qr, gross)
        q = quote_payin(package, gross, user, qr_account_id=locked_qr.pk)
    except ValueError as exc:
        raise ValidationError({'amount': str(exc)}) from exc

    contact = Contact.objects.filter(id=contact_id, user=user, is_deleted=False).first()
    if not contact:
        raise ValidationError({'contact_id': 'Contact not found.'})

    lm = None
    last_integrity: IntegrityError | None = None
    for attempt in range(2):
        tid = generate_service_id('load_money')
        try:
            lm = LoadMoney.objects.create(
                user=user,
                package=package,
                payment_gateway=None,
                collection_rail='qr',
                pay_in_qr_account=locked_qr,
                amount=gross,
                submitted_amount=gross,
                gateway=locked_qr.display_name,
                charge=q['total_deduction'],
                net_credit=q['net_credit'],
                fee_breakdown_snapshot=q['snapshot'],
                customer_name=contact.name,
                customer_email=contact.email,
                customer_phone=contact.phone,
                status='PENDING_REVIEW',
                transaction_id=tid,
                utr=utr_norm,
                payment_date=payment_date,
                receipt_image=receipt_file,
                payment_method='upi',
            )
            break
        except IntegrityError as exc:
            last_integrity = exc
            if 'utr' in str(exc).lower() or 'load_money_utr' in str(exc):
                raise ValidationError(
                    {'utr': 'This UTR already exists. Please verify and resubmit.'}
                ) from exc
            logger.warning('LoadMoney QR create collision on transaction_id (attempt %s)', attempt)
    if lm is None:
        raise TransactionFailed(
            'Could not allocate a unique pay-in reference; please retry.'
        ) from last_integrity

    return lm
