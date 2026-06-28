from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.bank_accounts.models import BankAccount, BankVerificationAttempt
from apps.bank_accounts.services import consume_validation_token, validate_bank_account
from apps.core.exceptions import BankValidationFailed
from apps.core.utils import encrypt_secret_payload
from apps.integrations.banking.types import BavVerifyResult
from apps.integrations.models import ApiMaster
from apps.transactions.models import PassbookEntry
from apps.wallets.models import Wallet

User = get_user_model()


def _bav_master():
    return ApiMaster.objects.create(
        provider_code='cashfree_bav',
        provider_name='Cashfree BAV',
        provider_type='banking',
        base_url='https://sandbox.cashfree.com',
        status='sandbox',
        is_default=True,
        config_json={'timeout': 10, 'use_mock': True},
        secrets_encrypted=encrypt_secret_payload({'client_id': 'cid', 'client_secret': 'csec'}),
    )


def _valid_result(name='JOHN DOE', ifsc='YESB0000001'):
    return BavVerifyResult(
        success=True,
        beneficiary_name=name,
        bank_name='YES BANK',
        branch='',
        city='',
        ifsc=ifsc,
        account_status='VALID',
        account_status_code='ACCOUNT_IS_VALID',
        name_match_score='',
        name_match_result='',
        reference_id='ref-1',
        utr='',
        raw={'mock': True},
    )


@override_settings(BANK_VERIFICATION_CHARGE=3.0)
class ValidateBankAccountServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555533',
            email='bavsvc@test.com',
            password='secret123',
            role='Retailer',
            user_id='BAVS01',
        )
        self.wallet = Wallet.get_wallet(self.user, 'main')
        self.wallet.balance = Decimal('100.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        _bav_master()

    def test_wallet_charged_only_on_success(self):
        opening = self.wallet.balance
        result = validate_bank_account(self.user, '1234567890', 'YESB0000001', '9555555533')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, opening - Decimal('3.00'))
        self.assertTrue(result['success'])
        self.assertTrue(result['validation_token'])
        self.assertIn('bank_account', result)
        attempt = BankVerificationAttempt.objects.get(user=self.user, status='consumed')
        self.assertTrue(attempt.wallet_charged)
        self.assertIsNotNone(attempt.bank_account_id)
        account = BankAccount.objects.get(user=self.user, account_number='1234567890')
        self.assertTrue(account.is_verified)
        self.assertEqual(account.beneficiary_name, result['beneficiary_name'])
        self.assertIn('reference_id', account.verification_details)
        self.assertEqual(PassbookEntry.objects.filter(user=self.user, service='BANK VERIFICATION').count(), 1)

    def test_insufficient_balance_blocks_validation(self):
        self.wallet.balance = Decimal('1.00')
        self.wallet.save(update_fields=['balance', 'updated_at'])
        with self.assertRaises(BankValidationFailed):
            validate_bank_account(self.user, '1234567890', 'YESB0000001', '9555555533')
        self.assertEqual(BankVerificationAttempt.objects.filter(user=self.user).count(), 0)
        self.assertEqual(PassbookEntry.objects.filter(user=self.user, service='BANK VERIFICATION').count(), 0)

    def test_failed_verification_does_not_charge_wallet(self):
        opening = self.wallet.balance
        with patch('apps.integrations.bank_validator.BankValidator.validate_account') as mock_verify:
            from apps.integrations.banking.exceptions import BavVerificationFailed

            mock_verify.side_effect = BavVerificationFailed('Invalid account', code='invalid')
            with self.assertRaises(BankValidationFailed):
                validate_bank_account(self.user, '1234567890', 'YESB0000001', '9555555533')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, opening)
        attempt = BankVerificationAttempt.objects.get(user=self.user, status='failed')
        self.assertFalse(attempt.wallet_charged)

    def test_validation_token_flow_for_create(self):
        result = validate_bank_account(self.user, '1234567890', 'YESB0000001', '9555555533')
        token = result['validation_token']
        account = BankAccount.objects.get(user=self.user, account_number='1234567890')
        self.assertTrue(account.is_verified)

        attempt = consume_validation_token(
            self.user,
            validation_token=token,
            account_number='1234567890',
            ifsc='YESB0000001',
        )
        self.assertEqual(attempt.status, 'consumed')
        self.assertEqual(attempt.bank_account_id, account.id)

    def test_invalid_validation_token_rejected(self):
        with self.assertRaises(BankValidationFailed):
            consume_validation_token(
                self.user,
                validation_token='bad-token',
                account_number='1234567890',
                ifsc='YESB0000001',
            )

    def test_duplicate_account_rejected_before_charge(self):
        BankAccount.objects.create(
            user=self.user,
            account_number='1234567890',
            ifsc='YESB0000001',
            bank_name='YES BANK',
            account_holder_name='JOHN DOE',
            beneficiary_name='JOHN DOE',
            is_verified=True,
        )
        opening = self.wallet.balance
        with self.assertRaises(BankValidationFailed) as ctx:
            validate_bank_account(self.user, '1234567890', 'YESB0000001', '9555555533')
        self.assertIn('already saved', str(ctx.exception).lower())
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, opening)

    def test_ifsc_corrected_and_saved_from_provider_response(self):
        corrected = _valid_result(ifsc='HDFC0001234')
        with patch('apps.integrations.bank_validator.BankValidator.validate_account', return_value=corrected):
            result = validate_bank_account(self.user, '1234567890', 'HDFC0009999', '9555555533')
        self.assertEqual(result['ifsc'], 'HDFC0001234')
        account = BankAccount.objects.get(user=self.user, account_number='1234567890')
        self.assertEqual(account.ifsc, 'HDFC0001234')
