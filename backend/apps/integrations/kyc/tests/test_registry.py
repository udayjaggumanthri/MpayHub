from django.test import TestCase

from apps.core.utils import encrypt_secret_payload
from apps.integrations.kyc.exceptions import KycConfigurationError
from apps.integrations.kyc.registry import infer_kyc_service, resolve_aadhaar_provider, resolve_pan_provider
from apps.integrations.models import ApiMaster


class KycRegistryTests(TestCase):
    def test_infer_kyc_service(self):
        self.assertEqual(infer_kyc_service('cashfree_pan'), 'pan')
        self.assertEqual(infer_kyc_service('cashfree_digilocker'), 'aadhaar')
        self.assertEqual(infer_kyc_service('unknown'), '')

    def test_resolve_pan_provider(self):
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
        provider = resolve_pan_provider()
        self.assertEqual(provider.provider_code, 'cashfree_pan')

    def test_resolve_aadhaar_provider(self):
        ApiMaster.objects.create(
            provider_code='cashfree_digilocker',
            provider_name='DL',
            provider_type='kyc',
            kyc_service='aadhaar',
            base_url='https://sandbox.cashfree.com',
            status='active',
            is_default=True,
            config_json={'redirect_url': 'https://partner.test/cb'},
            secrets_encrypted=encrypt_secret_payload({'client_id': 'a', 'client_secret': 'b'}),
        )
        provider = resolve_aadhaar_provider()
        self.assertEqual(provider.provider_code, 'cashfree_digilocker')

    def test_missing_provider_raises(self):
        with self.assertRaises(KycConfigurationError):
            resolve_pan_provider()
