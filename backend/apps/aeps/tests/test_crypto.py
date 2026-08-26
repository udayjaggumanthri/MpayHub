from django.test import SimpleTestCase

from apps.integrations.fingpay.crypto import (
    build_encrypted_request,
    build_recon_hash,
    build_simple_onboarding_hash,
    build_simple_txn_hash,
    build_status_check_hash,
    load_bundled_fingpay_certificate,
    looks_like_md5_hex,
    mask_aadhaar,
    md5_hex,
    resolve_password_md5,
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

    def test_scrub_for_tapits_keeps_full_images_and_aadhaar(self):
        pin_md5 = '81dc9bdb52d04dc20036dbd8313ed055'
        img = 'iVBORw0KGgoAAAANSUhEUgAAAoYAAAGrCAYAAABdUFYMAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8Y' + ('A' * 200)
        cleaned = scrub_sensitive(
            {
                'merchantLoginPin': pin_md5,
                'aadhaarNumber': '287663698750',
                'merchantPanImage': f'data:image/jpeg;base64,{img}',
                'maskedAadharImage': img,
                'backgroundImageOfShop': img,
            },
            for_tapits=True,
        )
        self.assertEqual(cleaned['merchantLoginPin'], pin_md5)
        self.assertEqual(cleaned['aadhaarNumber'], '287663698750')
        self.assertEqual(cleaned['merchantPanImage'], img)
        self.assertEqual(cleaned['maskedAadharImage'], img)
        self.assertEqual(cleaned['backgroundImageOfShop'], img)
        self.assertNotIn('total_len=', cleaned['merchantPanImage'])
        self.assertNotIn('data:', cleaned['merchantPanImage'])

    def test_recon_hash_stable(self):
        h1 = build_recon_hash(request_body='{}', super_merchant_login_id='demo', secret_key='secret')
        h2 = build_recon_hash(request_body='{}', super_merchant_login_id='demo', secret_key='secret')
        self.assertEqual(h1, h2)
        self.assertEqual(h1, sha256_b64('{}' + 'demo' + 'secret'))

    def test_resolve_password_md5_plain(self):
        self.assertEqual(resolve_password_md5('secret', mode='plain'), md5_hex('secret'))
        self.assertEqual(resolve_password_md5('secret', mode=''), md5_hex('secret'))

    def test_resolve_password_md5_already_hashed(self):
        digest = md5_hex('secret')
        self.assertTrue(looks_like_md5_hex(digest))
        self.assertEqual(resolve_password_md5(digest, mode='md5'), digest)
        self.assertEqual(resolve_password_md5(digest.upper(), mode='hashed'), digest.lower())

    def test_resolve_password_md5_mode_md5_but_plain_value(self):
        # Misconfigured: mode says md5 but value is not 32-hex — hash once
        self.assertEqual(resolve_password_md5('plain-password', mode='md5'), md5_hex('plain-password'))

    def test_simple_onboarding_hash(self):
        login = 'MpTest'
        pwd_md5 = md5_hex('secret')
        expected = sha256_b64(f'{login}@{pwd_md5}')
        self.assertEqual(
            build_simple_onboarding_hash(super_merchant_login_id=login, password_md5=pwd_md5),
            expected,
        )

    def test_simple_txn_hash(self):
        plain = '{"superMerchantId":1501,"merchantLoginId":"9550221153","transactionType":"EKY","mobileNumber":"9550221153","aadharNumber":"287663698750","panNumber":"KRAPK2170N","matmSerialNumber":"","latitude":17.4442488,"longitude":79.4808912}'
        ts = '2026-08-12 15:15:00'
        key = 'faee796c14b81d1e6d3c14c0a19bd7c1990b08f099efe93d4724f144d2e74a62'
        expected = 'VyGJADVfm1cGDga3+E1TuUt5cXo1GbLCr0P4aCh6vtw='
        self.assertEqual(
            build_simple_txn_hash(plain_json=plain, secret_key=key, trn_timestamp=ts),
            expected,
        )
        self.assertEqual(
            build_simple_txn_hash(plain_json=plain, secret_key=key, trn_timestamp=ts),
            sha256_b64(f'{plain}{key}{ts}'),
        )

    def test_status_check_hash_lowercases(self):
        h = build_status_check_hash(
            merchant_tran_id='Abc',
            merchant_login_id='Merch',
            super_merchant_login_id='Super',
        )
        self.assertEqual(h, sha256_b64('abc+merch+super'))

    def test_bundled_certificate_encrypts_cbc(self):
        pem = load_bundled_fingpay_certificate()
        self.assertIn('BEGIN CERTIFICATE', pem)
        enc = build_encrypted_request(plain_json='{"ok":true}', rsa_public_key_pem=pem, aes_mode='cbc')
        self.assertTrue(enc['body'])
        self.assertTrue(enc['eskey'])
        self.assertEqual(enc['hash'], sha256_b64('{"ok":true}'))

    def test_bundled_certificate_encrypts_ecb(self):
        pem = load_bundled_fingpay_certificate()
        enc = build_encrypted_request(plain_json='{"ok":true}', rsa_public_key_pem=pem, aes_mode='ecb')
        self.assertTrue(enc['body'])
        self.assertTrue(enc['eskey'])
