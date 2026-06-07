from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.utils import encrypt_secret_payload
from apps.integrations.kyc.cashfree_vrs_client import CashfreeVrsClient
from apps.integrations.kyc.exceptions import KycVerificationFailed
from apps.integrations.kyc.providers.cashfree_pan import CashfreePanProvider
from apps.integrations.models import ApiMaster

User = get_user_model()


def _pan_master(*, mode='sync', min_score=None):
    cfg = {'mode': mode, 'timeout': 10}
    if min_score is not None:
        cfg['min_name_match_score'] = min_score
    return ApiMaster.objects.create(
        provider_code='cashfree_pan',
        provider_name='Cashfree PAN',
        provider_type='kyc',
        kyc_service='pan',
        base_url='https://sandbox.cashfree.com',
        status='sandbox',
        is_default=True,
        config_json=cfg,
        secrets_encrypted=encrypt_secret_payload({'client_id': 'cid', 'client_secret': 'csec'}),
    )


class CashfreePanProviderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555511',
            email='pan@test.com',
            password='secret123',
            role='Retailer',
            user_id='PAN01',
        )
        self.master = _pan_master()

    def _provider(self, master=None):
        master = master or self.master
        client = CashfreeVrsClient(
            base_url=master.base_url,
            client_id='cid',
            client_secret='csec',
            timeout=10,
        )
        return CashfreePanProvider(master=master, client=client)

    def test_sync_valid_pan(self):
        provider = self._provider()
        with patch.object(provider.client, 'verify_pan_sync', return_value={
            'valid': True,
            'registered_name': 'JOHN DOE',
            'reference_id': 'ref1',
            'name_match_score': 95,
        }):
            result = provider.verify_pan(user=self.user, pan='ABCDE1234F', name='JOHN DOE')
        self.assertTrue(result.success)
        self.assertEqual(result.registered_name, 'JOHN DOE')

    def test_sync_invalid_pan_raises(self):
        provider = self._provider()
        with patch.object(provider.client, 'verify_pan_sync', return_value={
            'valid': False,
            'message': 'Invalid PAN',
        }):
            with self.assertRaises(KycVerificationFailed):
                provider.verify_pan(user=self.user, pan='ABCDE1234F', name='JOHN DOE')

    def test_advance_valid_pan(self):
        self.master.config_json = {'mode': 'advance', 'timeout': 10}
        self.master.save(update_fields=['config_json', 'updated_at'])
        provider = self._provider(self.master)
        with patch.object(provider.client, 'verify_pan_advance', return_value={
            'status': 'VALID',
            'registered_name': 'JANE DOE',
            'reference_id': 'ref2',
        }):
            result = provider.verify_pan(user=self.user, pan='ABCDE1234F', name='JANE DOE')
        self.assertTrue(result.success)
        self.assertRegex(result.verification_id, r'^PAN_[A-Za-z0-9]+_[a-f0-9]{12}$')

    def test_case_insensitive_name_accepted_despite_low_score(self):
        provider = self._provider()
        with patch.object(provider.client, 'verify_pan_sync', return_value={
            'valid': True,
            'registered_name': 'JOHN DOE',
            'name_match_score': 10,
            'name_match_result': 'NO_MATCH',
        }):
            result = provider.verify_pan(user=self.user, pan='ABCDE1234F', name='John Doe')
        self.assertTrue(result.success)
        self.assertEqual(result.registered_name, 'JOHN DOE')

    def test_name_mismatch_rejected_even_when_valid_true(self):
        provider = self._provider()
        with patch.object(provider.client, 'verify_pan_sync', return_value={
            'valid': True,
            'registered_name': 'JOHN DOE',
            'name_match_score': 95,
        }):
            with self.assertRaises(KycVerificationFailed):
                provider.verify_pan(user=self.user, pan='ABCDE1234F', name='JANE DOE')

    def test_name_match_score_rejection_when_pan_invalid(self):
        master = _pan_master(min_score=80)
        provider = self._provider(master)
        with patch.object(provider.client, 'verify_pan_sync', return_value={
            'valid': False,
            'name_match_score': 50,
            'message': 'Invalid PAN',
        }):
            with self.assertRaises(KycVerificationFailed):
                provider.verify_pan(user=self.user, pan='ABCDE1234F', name='JOHN DOE')
