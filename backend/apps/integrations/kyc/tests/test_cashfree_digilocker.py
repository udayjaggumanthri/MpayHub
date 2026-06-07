from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.utils import encrypt_secret_payload
from apps.integrations.kyc.cashfree_vrs_client import CashfreeVrsClient
from apps.integrations.kyc.providers.cashfree_digilocker import CashfreeDigilockerProvider
from apps.integrations.models import ApiMaster
from apps.users.models import KycDigilockerSession

User = get_user_model()


def _digilocker_master():
    return ApiMaster.objects.create(
        provider_code='cashfree_digilocker',
        provider_name='Cashfree DigiLocker',
        provider_type='kyc',
        kyc_service='aadhaar',
        base_url='https://sandbox.cashfree.com',
        status='sandbox',
        is_default=True,
        config_json={
            'redirect_url': 'https://partner.test/onboarding/kyc/digilocker/callback',
            'document_requested': ['AADHAAR'],
            'user_flow': 'signup',
            'timeout': 10,
        },
        secrets_encrypted=encrypt_secret_payload({'client_id': 'cid', 'client_secret': 'csec'}),
    )


class CashfreeDigilockerProviderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555522',
            email='dl@test.com',
            password='secret123',
            role='Retailer',
            user_id='DL01',
        )
        self.master = _digilocker_master()
        self.client = CashfreeVrsClient(
            base_url=self.master.base_url,
            client_id='cid',
            client_secret='csec',
            timeout=10,
        )
        self.provider = CashfreeDigilockerProvider(master=self.master, client=self.client)

    def test_init_session_creates_row_and_returns_url(self):
        with patch.object(self.provider.client, 'digilocker_create_url', return_value={
            'url': 'https://digilocker.example/consent',
            'reference_id': 'r1',
            'status': 'PENDING',
            'user_flow': 'signup',
        }):
            result = self.provider.init_session(user=self.user)
        self.assertEqual(result.url, 'https://digilocker.example/consent')
        self.assertTrue(result.verification_id)
        session = KycDigilockerSession.objects.get(verification_id=result.verification_id)
        self.assertEqual(session.user_id, self.user.pk)
        self.assertEqual(session.status, 'PENDING')

    def test_init_with_aadhaar_calls_verify_account(self):
        with patch.object(self.provider.client, 'digilocker_verify_account', return_value={'status': 'OK'}) as mock_va, \
             patch.object(self.provider.client, 'digilocker_create_url', return_value={
                 'url': 'https://digilocker.example/consent',
                 'status': 'PENDING',
             }):
            self.provider.init_session(user=self.user, aadhaar_number='123456789012')
        mock_va.assert_called_once()

    def test_get_status_updates_session(self):
        session = KycDigilockerSession.objects.create(
            user=self.user,
            verification_id='DLTEST001',
            status='PENDING',
            provider_code='cashfree_digilocker',
        )
        with patch.object(self.provider.client, 'digilocker_get_status', return_value={
            'status': 'AUTHENTICATED',
            'reference_id': 'r2',
        }):
            result = self.provider.get_status(verification_id='DLTEST001')
        session.refresh_from_db()
        self.assertEqual(result.status, 'AUTHENTICATED')
        self.assertEqual(session.status, 'AUTHENTICATED')

    def test_fetch_document_masks_uid(self):
        with patch.object(self.provider.client, 'digilocker_get_document', return_value={
            'status': 'SUCCESS',
            'uid': '123456789012',
            'name': 'Test User',
        }):
            doc = self.provider.fetch_document(verification_id='DLTEST001', document_type='AADHAAR')
        self.assertEqual(doc.uid_masked, 'XXXX9012')
