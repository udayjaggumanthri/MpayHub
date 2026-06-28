"""
Bank account business logic services.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.bank_accounts.models import BankAccount, BankVerificationAttempt
from apps.core.exceptions import BankValidationFailed
from apps.core.utils import generate_service_id, validate_ifsc, validate_phone
from apps.integrations.bank_validator import BankValidator
from apps.integrations.banking.exceptions import (
    BavConfigurationError,
    BavProviderError,
    BavVerificationFailed,
)
from apps.integrations.banking.types import BavVerifyResult
from apps.transactions.models import PassbookEntry
from apps.wallets.models import Wallet

VALIDATION_TOKEN_TTL_MINUTES = 10


def _map_bav_exception(exc: Exception) -> BankValidationFailed:
    if isinstance(exc, (BavVerificationFailed, BavConfigurationError, BavProviderError)):
        return BankValidationFailed(str(exc))
    return BankValidationFailed('Bank account validation failed. Please try again.')


def _build_verification_details(result: BavVerifyResult) -> dict:
    raw = result.raw if isinstance(result.raw, dict) else {}
    ifsc_details = raw.get('ifsc_details')
    if not isinstance(ifsc_details, dict):
        ifsc_details = {}
    return {
        'reference_id': result.reference_id,
        'name_at_bank': result.beneficiary_name,
        'bank_name': result.bank_name,
        'city': result.city,
        'branch': result.branch,
        'micr': raw.get('micr'),
        'name_match_score': result.name_match_score,
        'name_match_result': result.name_match_result,
        'account_status': result.account_status,
        'account_status_code': result.account_status_code,
        'utr': result.utr or raw.get('utr') or '',
        'ifsc_details': ifsc_details,
    }


def _build_attempt_response_meta(result: BavVerifyResult) -> dict:
    details = _build_verification_details(result)
    details['beneficiary_name'] = result.beneficiary_name
    return details


def save_verified_bank_account(
    user,
    *,
    account_number: str,
    ifsc: str,
    result: BavVerifyResult,
    provider_code: str,
    mobile_number: str = '',
) -> BankAccount:
    """Persist verified bank account details from a successful Cashfree BAV response."""
    resolved_ifsc = str(result.ifsc or ifsc).upper().strip()
    verification_details = _build_verification_details(result)
    bank_name = str(result.bank_name or verification_details.get('bank_name') or '').strip()
    if not bank_name:
        ifsc_details = verification_details.get('ifsc_details') or {}
        if isinstance(ifsc_details, dict):
            bank_name = str(ifsc_details.get('bank') or '').strip()

    account, _created = BankAccount.objects.update_or_create(
        user=user,
        account_number=account_number,
        ifsc=resolved_ifsc,
        defaults={
            'bank_name': bank_name or 'UNKNOWN',
            'account_holder_name': result.beneficiary_name,
            'beneficiary_name': result.beneficiary_name,
            'is_verified': True,
            'verification_reference_id': str(result.reference_id or ''),
            'provider_code': provider_code,
            'branch': result.branch,
            'city': result.city,
            'name_match_score': str(result.name_match_score or ''),
            'name_match_result': str(result.name_match_result or ''),
            'verification_details': verification_details,
            'verified_at': timezone.now(),
            'mobile_number': mobile_number,
        },
    )
    return account


def _ensure_account_not_duplicate(user, account_number: str, ifsc: str) -> None:
    exists = BankAccount.objects.filter(
        user=user,
        account_number=account_number,
        ifsc=ifsc.upper(),
        is_deleted=False,
    ).exists()
    if exists:
        raise BankValidationFailed(
            'This bank account is already saved in your profile. '
            'View it in Bank Accounts or delete the existing entry before validating again.'
        )


def _charge_verification_fee(user, *, account_number: str, ifsc: str) -> None:
    main_wallet = Wallet.get_wallet(user, 'main')
    verification_charge = Decimal(str(settings.BANK_VERIFICATION_CHARGE))
    service_id = f"BV{generate_service_id('bank_verify')}"
    opening_balance = main_wallet.balance
    main_wallet.debit(verification_charge, reference=service_id)
    closing_balance = main_wallet.balance
    PassbookEntry.objects.create(
        user=user,
        wallet_type='main',
        service='BANK VERIFICATION',
        service_id=service_id,
        description=f"BANK VERIFICATION for A/C: {account_number[-4:]}, IFSC: {ifsc}",
        debit_amount=verification_charge,
        credit_amount=Decimal('0.00'),
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        service_charge=Decimal('0.00'),
        principal_amount=verification_charge,
    )


def _build_validate_response(
    result: BavVerifyResult,
    *,
    account_number: str,
    ifsc: str,
    validation_token: str,
    bank_account: BankAccount | None = None,
) -> dict:
    payload = {
        'success': True,
        'beneficiary_name': result.beneficiary_name,
        'account_number': account_number,
        'ifsc': ifsc,
        'bank_name': result.bank_name,
        'reference_id': result.reference_id,
        'name_match_score': result.name_match_score,
        'name_match_result': result.name_match_result,
        'validation_token': validation_token,
        'verification_details': _build_verification_details(result),
    }
    if bank_account is not None:
        from apps.bank_accounts.serializers import BankAccountSerializer

        payload['bank_account'] = BankAccountSerializer(bank_account).data
    return payload


def validate_bank_account(user, account_number, ifsc, mobile_number=''):
    """
    Validate bank account and fetch beneficiary name.

    Wallet is charged only after successful VALID verification.
    """
    account_number = str(account_number or '').strip()
    ifsc = str(ifsc or '').upper().strip()
    mobile = str(mobile_number or '').strip()
    if not mobile or not validate_phone(mobile):
        raise BankValidationFailed('A valid 10-digit mobile number is required.')
    if not validate_ifsc(ifsc):
        raise BankValidationFailed('Invalid IFSC code format.')
    _ensure_account_not_duplicate(user, account_number, ifsc)
    main_wallet = Wallet.get_wallet(user, 'main')
    verification_charge = Decimal(str(settings.BANK_VERIFICATION_CHARGE))
    if main_wallet.balance < verification_charge:
        raise BankValidationFailed('Insufficient balance for verification charge.')

    phone = mobile
    bank_validator = BankValidator()
    provider_code = ''
    reference_id = ''
    validation_token = uuid.uuid4().hex
    expires_at = timezone.now() + timezone.timedelta(minutes=VALIDATION_TOKEN_TTL_MINUTES)

    try:
        provider_code = bank_validator.provider_code
        result = bank_validator.validate_account(
            account_number,
            ifsc,
            user=user,
            phone=phone,
        )
        reference_id = result.reference_id
        resolved_ifsc = str(result.ifsc or ifsc).upper().strip()
        if resolved_ifsc != ifsc:
            _ensure_account_not_duplicate(user, account_number, resolved_ifsc)
    except (BavVerificationFailed, BavConfigurationError, BavProviderError) as exc:
        BankVerificationAttempt.objects.create(
            user=user,
            provider_code=provider_code,
            reference_id=reference_id,
            account_number_last4=account_number[-4:] if account_number else '',
            ifsc=ifsc,
            status='failed',
            validation_token='',
            validation_token_expires_at=None,
            request_meta={
                'account_number_last4': account_number[-4:] if account_number else '',
                'ifsc': ifsc,
                'mobile_number': mobile,
            },
            response_meta=getattr(exc, 'details', {}) or {},
            wallet_charged=False,
        )
        raise _map_bav_exception(exc) from exc
    except Exception as exc:
        BankVerificationAttempt.objects.create(
            user=user,
            provider_code=provider_code,
            reference_id=reference_id,
            account_number_last4=account_number[-4:] if account_number else '',
            ifsc=ifsc,
            status='failed',
            validation_token='',
            validation_token_expires_at=None,
            request_meta={
                'account_number_last4': account_number[-4:] if account_number else '',
                'ifsc': ifsc,
            },
            response_meta={'error': str(exc)[:500]},
            wallet_charged=False,
        )
        raise BankValidationFailed('Bank account validation failed. Please try again.') from exc

    with db_transaction.atomic():
        _charge_verification_fee(user, account_number=account_number, ifsc=resolved_ifsc)
        bank_account = save_verified_bank_account(
            user,
            account_number=account_number,
            ifsc=resolved_ifsc,
            result=result,
            provider_code=provider_code,
            mobile_number=mobile,
        )
        attempt = BankVerificationAttempt.objects.create(
            user=user,
            provider_code=provider_code,
            reference_id=reference_id,
            account_number_last4=account_number[-4:] if account_number else '',
            ifsc=resolved_ifsc,
            status='consumed',
            validation_token=validation_token,
            validation_token_expires_at=expires_at,
            request_meta={
                'account_number_last4': account_number[-4:] if account_number else '',
                'ifsc_submitted': ifsc,
                'ifsc_resolved': resolved_ifsc,
                'mobile_number': mobile,
            },
            response_meta=_build_attempt_response_meta(result),
            wallet_charged=True,
            bank_account=bank_account,
        )

    return _build_validate_response(
        result,
        account_number=account_number,
        ifsc=resolved_ifsc,
        validation_token=validation_token,
        bank_account=bank_account,
    )


def consume_validation_token(user, *, validation_token: str, account_number: str, ifsc: str) -> BankVerificationAttempt:
    """Validate and consume a short-lived validation receipt for bank account create."""
    token = str(validation_token or '').strip()
    if not token:
        raise BankValidationFailed('Bank account must be validated before saving.')

    account_number = str(account_number or '').strip()
    ifsc = str(ifsc or '').upper().strip()
    now = timezone.now()

    with db_transaction.atomic():
        attempt = (
            BankVerificationAttempt.objects.select_for_update()
            .filter(
                user=user,
                validation_token=token,
                status__in=('validated', 'consumed'),
                is_deleted=False,
            )
            .order_by('-created_at')
            .first()
        )
        if attempt is None:
            raise BankValidationFailed('Invalid or expired validation. Please validate the account again.')
        if attempt.validation_token_expires_at and attempt.validation_token_expires_at < now:
            raise BankValidationFailed('Validation expired. Please validate the account again.')
        if attempt.account_number_last4 != (account_number[-4:] if len(account_number) >= 4 else account_number):
            raise BankValidationFailed('Validation token does not match this account number.')
        if attempt.ifsc.upper() != ifsc:
            raise BankValidationFailed('Validation token does not match this IFSC code.')

        if attempt.bank_account_id:
            if attempt.status != 'consumed':
                attempt.status = 'consumed'
                attempt.save(update_fields=['status', 'updated_at'])
            return attempt

        if attempt.status != 'consumed':
            attempt.status = 'consumed'
            attempt.save(update_fields=['status', 'updated_at'])
        return attempt
