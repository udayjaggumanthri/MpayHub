import base64
import hashlib
import hmac
import json
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.utils import encrypt_secret_payload
from apps.integrations.kyc.types import DigilockerDocumentResult
from apps.integrations.kyc.webhooks import handle_digilocker_webhook, verify_cashfree_webhook_signature
from apps.integrations.models import ApiMaster
from apps.users.models import KYC, KycDigilockerSession

User = get_user_model()


def _sign_body(raw_body: bytes, secret: str, timestamp: str = '1710000000') -> str:
    message = f'{timestamp}{raw_body.decode("utf-8")}'.encode('utf-8')
    digest = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode('utf-8')


class CashfreeDigilockerWebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555533',
            email='wh@test.com',
            password='secret123',
            role='Retailer',
            user_id='WH01',
        )
        KYC.objects.create(user=self.user, pan='ABCDE1234F', pan_verified=True)
        self.session = KycDigilockerSession.objects.create(
            user=self.user,
            verification_id='DLWH001',
            status='PENDING',
            provider_code='cashfree_digilocker',
        )
        ApiMaster.objects.create(
            provider_code='cashfree_digilocker',
            provider_name='DL',
            provider_type='kyc',
            kyc_service='aadhaar',
            base_url='https://sandbox.cashfree.com',
            status='active',
            is_default=True,
            config_json={'redirect_url': 'https://partner.test/cb', 'webhook_secret': 'whsec_test'},
            secrets_encrypted=encrypt_secret_payload({'client_id': 'a', 'client_secret': 'b'}),
        )
        self.client = APIClient()

    def test_signature_verification(self):
        body = b'{"event_type":"TEST"}'
        sig = _sign_body(body, 'whsec_test')
        self.assertTrue(verify_cashfree_webhook_signature(body, sig, '1710000000', 'whsec_test'))
        self.assertFalse(verify_cashfree_webhook_signature(body, 'bad', '1710000000', 'whsec_test'))

    @patch('apps.integrations.kyc.webhooks.resolve_aadhaar_provider')
    def test_handle_webhook_marks_aadhaar_verified(self, mock_resolve):
        mock_provider = mock_resolve.return_value
        mock_provider.fetch_document.return_value = DigilockerDocumentResult(
            verification_id='DLWH001',
            status='SUCCESS',
            uid_masked='XXXX9012',
            name='Test',
            raw={},
        )
        payload = {
            'event_type': 'DIGILOCKER_VERIFICATION_SUCCESS',
            'data': {
                'verification_id': 'DLWH001',
                'status': 'AUTHENTICATED',
                'reference_id': 'r1',
            },
        }
        handle_digilocker_webhook(payload)
        self.session.refresh_from_db()
        self.user.kyc.refresh_from_db()
        self.assertEqual(self.session.status, 'AUTHENTICATED')
        self.assertTrue(self.user.kyc.aadhaar_verified)

    def test_webhook_rejected_without_secret(self):
        master = ApiMaster.objects.get(provider_code='cashfree_digilocker')
        master.config_json = {'redirect_url': 'https://partner.test/cb'}
        master.save(update_fields=['config_json', 'updated_at'])
        payload = {'event_type': 'TEST', 'data': {}}
        raw = json.dumps(payload).encode('utf-8')
        resp = self.client.post(
            '/api/integrations/cashfree/digilocker/webhook/',
            data=raw,
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE='sig',
            HTTP_X_WEBHOOK_TIMESTAMP='1710000000',
        )
        self.assertEqual(resp.status_code, 401)

    @patch('apps.integrations.kyc.webhooks.resolve_aadhaar_provider')
    def test_webhook_rejects_aadhaar_without_pan_verified(self, mock_resolve):
        self.user.kyc.pan_verified = False
        self.user.kyc.save(update_fields=['pan_verified', 'updated_at'])
        mock_provider = mock_resolve.return_value
        mock_provider.fetch_document.return_value = DigilockerDocumentResult(
            verification_id='DLWH001',
            status='SUCCESS',
            uid_masked='XXXX9012',
            name='Test',
            raw={},
        )
        payload = {
            'event_type': 'DIGILOCKER_VERIFICATION_SUCCESS',
            'data': {'verification_id': 'DLWH001', 'status': 'AUTHENTICATED'},
        }
        result = handle_digilocker_webhook(payload)
        self.user.kyc.refresh_from_db()
        self.assertFalse(result.get('handled', True))
        self.assertFalse(self.user.kyc.aadhaar_verified)

    @patch('apps.integrations.kyc.webhooks.resolve_aadhaar_provider')
    def test_webhook_endpoint_idempotent(self, mock_resolve):
        mock_provider = mock_resolve.return_value
        mock_provider.fetch_document.return_value = DigilockerDocumentResult(
            verification_id='DLWH001',
            status='SUCCESS',
            uid_masked='XXXX9012',
            name='Test',
            raw={},
        )
        payload = {
            'event_type': 'DIGILOCKER_VERIFICATION_SUCCESS',
            'data': {
                'verification_id': 'DLWH001',
                'status': 'AUTHENTICATED',
            },
        }
        raw = json.dumps(payload).encode('utf-8')
        ts = str(int(time.time()))
        sig = _sign_body(raw, 'whsec_test', timestamp=ts)
        for _ in range(2):
            resp = self.client.post(
                '/api/integrations/cashfree/digilocker/webhook/',
                data=raw,
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=sig,
                HTTP_X_WEBHOOK_TIMESTAMP=ts,
            )
            self.assertEqual(resp.status_code, 200)
        self.user.kyc.refresh_from_db()
        self.assertTrue(self.user.kyc.aadhaar_verified)
