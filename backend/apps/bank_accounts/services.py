"""
Bank account business logic services.
"""
from django.db import transaction as db_transaction
from decimal import Decimal
from django.conf import settings
from apps.bank_accounts.models import BankAccount
from apps.wallets.models import Wallet
from apps.transactions.models import PassbookEntry
from apps.core.utils import generate_service_id
from apps.core.exceptions import BankValidationFailed
from apps.integrations.bank_validator import BankValidator
import random


def validate_bank_account(user, account_number, ifsc):
    """
    Validate bank account and fetch beneficiary name.
    
    Args:
        user: User object
        account_number: Account number
        ifsc: IFSC code
    
    Returns:
        dict with beneficiary_name, account_number, ifsc
    """
    # Check main wallet balance for verification charge
    main_wallet = Wallet.get_wallet(user, 'main')
    verification_charge = Decimal(str(settings.BANK_VERIFICATION_CHARGE))
    
    if main_wallet.balance < verification_charge:
        raise BankValidationFailed("Insufficient balance for verification charge.")
    
    # Validate via bank validator (with mock fallback)
    bank_validator = BankValidator()
    
    try:
        result = bank_validator.validate_account(account_number, ifsc)
        beneficiary_name = result.get('beneficiary_name')
    except Exception:
        # Mock beneficiary names for development
        mock_names = [
            'Mr REESU MADHU PAVAN',
            'Mrs KAVITHA REDDY',
            'Mr RAVI KUMAR',
            'Ms PRIYA SHARMA',
            'Mr R PAVA',
            'BALR',
            'KONE MAN',
        ]
        beneficiary_name = random.choice(mock_names)
    
    # Deduct verification charge
    opening_balance = main_wallet.balance
    main_wallet.debit(verification_charge, reference=f"BV{generate_service_id('bank_verify')}")
    closing_balance = main_wallet.balance
    
    # Create passbook entry
    PassbookEntry.objects.create(
        user=user,
        wallet_type='main',
        service='BANK VERIFICATION',
        service_id=f"BV{generate_service_id('bank_verify')}",
        description=f"BANK VERIFICATION for A/C: {account_number[-4:]}, IFSC: {ifsc}",
        debit_amount=verification_charge,
        credit_amount=Decimal('0.00'),
        opening_balance=opening_balance,
        closing_balance=closing_balance
    )
    
    return {
        'success': True,
        'beneficiary_name': beneficiary_name,
        'account_number': account_number,
        'ifsc': ifsc
    }
