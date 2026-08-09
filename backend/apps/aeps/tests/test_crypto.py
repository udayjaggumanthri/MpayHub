from django.test import SimpleTestCase

from apps.integrations.fingpay.crypto import (
    build_encrypted_request,
    build_recon_hash,
    load_bundled_fingpay_certificate,
    mask_aadhaar,
    scrub_sensitive,
    sha256_b64,
)


class FingpayCryptoTests(SimpleTestCase):
    def test_mask_aadhaar(self):
        self.assertEqual(mask_aadhaar('123456789012'), 'xxxxxxxx9012')

    def test_scrub_sensitive(self):
        cleaned = scrub_sensitive({'aadhaarNumber': '1234', 'bank': 'SBI', 'captureResponse': {'Piddata': 'x'}})
        self.assertEqual(cleaned['aadhaarNumber'], '[REDACTED]')
        self.assertEqual(cleaned['bank'], 'SBI')
        self.assertEqual(cleaned['captureResponse'], '[REDACTED]')

    def test_scrub_for_tapits_shows_md5_pin_and_image_preview(self):
        pin_md5 = '81dc9bdb52d04dc20036dbd8313ed055'
        img = 'iVBORw0KGgoAAAANSUhEUgAAAoYAAAGrCAYAAABdUFYMAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8Y' + ('A' * 200)
        cleaned = scrub_sensitive(
            {
                'merchantLoginPin': pin_md5,
                'aadhaarNumber': '287663698750',
                'merchantPanImage': img,
                'maskedAadharImage': img,
                'backgroundImageOfShop': img,
            },
            for_tapits=True,
        )
        self.assertEqual(cleaned['merchantLoginPin'], pin_md5)
        self.assertEqual(cleaned['aadhaarNumber'], 'xxxxxxxx8750')
        self.assertTrue(cleaned['merchantPanImage'].startswith('iVBORw0KGgo'))
        self.assertIn('total_len=', cleaned['merchantPanImage'])
        self.assertTrue(cleaned['maskedAadharImage'].startswith('iVBORw0KGgo'))
        self.assertTrue(cleaned['backgroundImageOfShop'].startswith('iVBORw0KGgo'))

    def test_recon_hash_stable(self):
        h1 = build_recon_hash(request_body='{}', super_merchant_login_id='demo', secret_key='secret')
        h2 = build_recon_hash(request_body='{}', super_merchant_login_id='demo', secret_key='secret')
        self.assertEqual(h1, h2)
        self.assertEqual(h1, sha256_b64('{}' + 'demo' + 'secret'))

    def test_bundled_certificate_encrypts_cbc(self):
        pem = load_bundled_fingpay_certificate()
        self.assertIn('BEGIN CERTIFICATE', pem)
        enc = build_encrypted_request(plain_json='{"ok":true}', rsa_public_key_pem=pem, aes_mode='cbc')
        self.assertTrue(enc['body'])
        self.assertTrue(enc['eskey'])
        self.assertEqual(enc['hash'], sha256_b64('{"ok":true}'))
