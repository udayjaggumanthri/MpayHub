from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.utils import encrypt_secret_payload
from apps.integrations.kyc.types import DigilockerDocumentResult, PanVerifyResult
from apps.integrations.models import ApiMaster
from apps.users.models import KYC, KycDigilockerSession, KycVerificationAttempt
from apps.users.services import complete_digilocker_aadhaar, self_service_verify_pan

User = get_user_model()


def _seed_kyc_masters():
    ApiMaster.objects.create(
        provider_code='cashfree_pan',
        provider_name='PAN',
        provider_type='kyc',
        kyc_service='pan',
        base_url='https://sandbox.cashfree.com',
        status='sandbox',
        is_default=True,
        config_json={'mode': 'sync'},
        secrets_encrypted=encrypt_secret_payload({'client_id': 'a', 'client_secret': 'b'}),
    )
    ApiMaster.objects.create(
        provider_code='cashfree_digilocker',
        provider_name='DL',
        provider_type='kyc',
        kyc_service='aadhaar',
        base_url='https://sandbox.cashfree.com',
        status='sandbox',
        is_default=True,
        config_json={'redirect_url': 'https://partner.test/cb'},
        secrets_encrypted=encrypt_secret_payload({'client_id': 'a', 'client_secret': 'b'}),
    )


class KycCashfreeFlowTests(TestCase):
    def setUp(self):
        _seed_kyc_masters()
        self.user = User.objects.create_user(
            phone='9555555544',
            email='flow@test.com',
            password='secret123',
            role='Retailer',
            user_id='FLOW01',
        )

    @patch('apps.integrations.kyc.registry.resolve_pan_provider')
    def test_self_service_verify_pan_creates_attempt(self, mock_resolve):
        mock_provider = mock_resolve.return_value
        mock_provider.provider_code = 'cashfree_pan'
        mock_provider.verify_pan.return_value = PanVerifyResult(
            success=True,
            pan='ABCDE1234F',
            registered_name='FLOW USER',
            reference_id='r1',
            verification_id='',
            status='VALID',
            message='OK',
            raw={},
        )
        kyc, kyc_details = self_service_verify_pan(self.user, 'ABCDE1234F', name='FLOW USER')
        self.assertTrue(kyc.pan_verified)
        self.assertEqual(kyc_details.get('name'), 'FLOW USER')
        self.assertEqual(KycVerificationAttempt.objects.filter(user=self.user).count(), 1)

    @patch('apps.integrations.kyc.registry.resolve_aadhaar_provider')
    def test_digilocker_complete_triggers_kyc_email(self, mock_resolve):
        KYC.objects.create(user=self.user, pan='ABCDE1234F', pan_verified=True)
        KycDigilockerSession.objects.create(
            user=self.user,
            verification_id='DLFLOW01',
            status='AUTHENTICATED',
            provider_code='cashfree_digilocker',
        )
        mock_provider = mock_resolve.return_value
        mock_provider.provider_code = 'cashfree_digilocker'
        mock_provider.complete_if_authenticated.return_value = DigilockerDocumentResult(
            verification_id='DLFLOW01',
            status='SUCCESS',
            uid_masked='XXXX9012',
            name='Flow User',
            raw={},
        )

        with patch('apps.notifications.services.email_dispatch.EmailNotificationService.dispatch') as mock_dispatch:
            kyc, kyc_details = complete_digilocker_aadhaar(self.user, 'DLFLOW01')
            self.assertTrue(kyc_details.get('aadhaar_masked'))
            self.assertTrue(kyc.aadhaar_verified)
            self.assertEqual(kyc.verification_status, 'verified')
            mock_dispatch.assert_called_once()
            self.assertEqual(mock_dispatch.call_args[0][0], 'kyc.verification.complete')
