from django.test import SimpleTestCase

from apps.integrations.fingpay.crypto import mask_aadhaar, scrub_sensitive, sha256_b64, build_recon_hash


class FingpayCryptoTests(SimpleTestCase):
    def test_mask_aadhaar(self):
        self.assertEqual(mask_aadhaar('123456789012'), 'xxxxxxxx9012')

    def test_scrub_sensitive(self):
        cleaned = scrub_sensitive({'aadhaarNumber': '1234', 'bank': 'SBI', 'captureResponse': {'Piddata': 'x'}})
        self.assertEqual(cleaned['aadhaarNumber'], '[REDACTED]')
        self.assertEqual(cleaned['bank'], 'SBI')
        self.assertEqual(cleaned['captureResponse'], '[REDACTED]')

    def test_recon_hash_stable(self):
        h1 = build_recon_hash(request_body='{}', super_merchant_login_id='demo', secret_key='secret')
        h2 = build_recon_hash(request_body='{}', super_merchant_login_id='demo', secret_key='secret')
        self.assertEqual(h1, h2)
        self.assertEqual(h1, sha256_b64('{}' + 'demo' + 'secret'))
