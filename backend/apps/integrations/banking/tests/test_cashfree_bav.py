from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.utils import encrypt_secret_payload
from apps.integrations.banking.exceptions import BavConfigurationError, BavVerificationFailed
from apps.integrations.banking.providers.cashfree_bav import CashfreeBavProvider
from apps.integrations.banking.registry import resolve_bav_provider
from apps.integrations.kyc.cashfree_vrs_client import CashfreeVrsClient
from apps.integrations.models import ApiMaster

User = get_user_model()


def _bav_master(*, use_mock=False):
    cfg = {'timeout': 10}
    if use_mock:
        cfg['use_mock'] = True
    return ApiMaster.objects.create(
        provider_code='cashfree_bav',
        provider_name='Cashfree BAV',
        provider_type='banking',
        base_url='https://sandbox.cashfree.com',
        status='sandbox',
        is_default=True,
        config_json=cfg,
        secrets_encrypted=encrypt_secret_payload({'client_id': 'cid', 'client_secret': 'csec'}),
    )


class CashfreeBavProviderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555522',
            email='bav@test.com',
            password='secret123',
            role='Retailer',
            user_id='BAV01',
        )
        self.master = _bav_master()

    def _provider(self, master=None):
        master = master or self.master
        client = CashfreeVrsClient(
            base_url=master.base_url,
            client_id='cid',
            client_secret='csec',
            timeout=10,
        )
        return CashfreeBavProvider(master=master, client=client)

    def test_valid_response_mapping(self):
        provider = self._provider()
        with patch.object(provider.client, 'verify_bank_account_sync', return_value={
            'account_status': 'VALID',
            'account_status_code': 'ACCOUNT_IS_VALID',
            'name_at_bank': 'JOHN DOE',
            'bank_name': 'YES BANK',
            'branch': 'MG ROAD',
            'city': 'BANGALORE',
            'reference_id': '34',
        }) as mock_verify:
            result = provider.verify(
                user=self.user,
                account_number='1234567890',
                ifsc='YESB0000001',
            )
        mock_verify.assert_called_once_with(
            bank_account='1234567890',
            ifsc='YESB0000001',
            phone='',
        )
        self.assertTrue(result.success)
        self.assertEqual(result.beneficiary_name, 'JOHN DOE')
        self.assertEqual(result.bank_name, 'YES BANK')
        self.assertEqual(result.ifsc, 'YESB0000001')
        self.assertEqual(result.reference_id, '34')

    def test_invalid_account_raises(self):
        provider = self._provider()
        with patch.object(provider.client, 'verify_bank_account_sync', return_value={
            'account_status': 'INVALID',
            'account_status_code': 'INVALID_ACCOUNT',
            'message': 'Invalid account',
        }):
            with self.assertRaises(BavVerificationFailed):
                provider.verify(
                    user=self.user,
                    account_number='1234567890',
                    ifsc='YESB0000001',
                )

    def test_low_name_score_still_succeeds(self):
        provider = self._provider()
        with patch.object(provider.client, 'verify_bank_account_sync', return_value={
            'account_status': 'VALID',
            'account_status_code': 'ACCOUNT_IS_VALID',
            'name_at_bank': 'JOHN DOE',
            'name_match_score': '10.00',
            'name_match_result': 'NO_MATCH',
        }):
            result = provider.verify(
                user=self.user,
                account_number='1234567890',
                ifsc='YESB0000001',
            )
        self.assertTrue(result.success)
        self.assertEqual(result.beneficiary_name, 'JOHN DOE')

    def test_ifsc_corrected_from_response(self):
        provider = self._provider()
        with patch.object(provider.client, 'verify_bank_account_sync', return_value={
            'account_status': 'VALID',
            'account_status_code': 'ACCOUNT_IS_VALID',
            'name_at_bank': 'JOHN DOE',
            'bank_name': 'HDFC BANK',
            'ifsc_details': {'ifsc': 'HDFC0001234', 'bank': 'HDFC BANK'},
        }):
            result = provider.verify(
                user=self.user,
                account_number='1234567890',
                ifsc='HDFC0009999',
            )
        self.assertEqual(result.ifsc, 'HDFC0001234')
        self.assertEqual(result.bank_name, 'HDFC BANK')

    def test_sandbox_mock_when_configured(self):
        self.master.config_json = {'timeout': 10, 'use_mock': True}
        self.master.save(update_fields=['config_json', 'updated_at'])
        provider = self._provider(self.master)
        result = provider.verify(
            user=self.user,
            account_number='1234567890',
            ifsc='YESB0000001',
        )
        self.assertTrue(result.success)
        self.assertEqual(result.beneficiary_name, 'SANDBOX BENEFICIARY')


class BavRegistryTests(TestCase):
    def test_missing_apimaster_raises(self):
        with self.assertRaises(BavConfigurationError):
            resolve_bav_provider()

    def test_resolve_default_banking_provider(self):
        _bav_master()
        provider = resolve_bav_provider()
        self.assertEqual(provider.provider_code, 'cashfree_bav')
