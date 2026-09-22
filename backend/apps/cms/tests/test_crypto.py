"""Unit tests for Uber CMS crypto (launch encrypt + inbound hash)."""
from __future__ import annotations

import base64
import json
import unittest

from apps.cms.services.crypto import (
    build_inbound_hash,
    build_launch_url,
    decode_skey,
    encrypt_launch_payload,
    verify_inbound_hash,
)


class CmsCryptoTests(unittest.TestCase):
    def test_decode_skey_aes256_from_doc_sample(self):
        # Live sample from Web URL doc
        skey = 'NDU2ZmEyNTQzNDQ2Y2RhMTgwM2I0ZWRlMzJjZDkyM2I='
        key = decode_skey(skey)
        self.assertEqual(len(key), 32)
        self.assertEqual(key, b'456fa2543446cda1803b4ede32cd923b')

    def test_encrypt_launch_payload_is_double_base64(self):
        # Use a proper 16-byte key encoded as Base64
        key_bytes = b'0123456789abcdef'
        skey = base64.b64encode(key_bytes).decode('ascii')
        payload = {
            'additionalParams': None,
            'latitude': 17.44,
            'loginType': '2',
            'longitude': 78.48,
            'supermerchantId': '2',
            'merchantId': 'swetha',
            'merchantPin': 'swetha',
            'mobileNumber': '8790861159',
            'amount': '2',
            'superMerchantSkey': skey,
        }
        encrypted = encrypt_launch_payload(payload, super_merchant_skey=skey)
        # Outer decode must yield ASCII Base64 of ciphertext
        inner = base64.b64decode(encrypted).decode('ascii')
        ciphertext = base64.b64decode(inner)
        self.assertGreater(len(ciphertext), 16)
        # Must be PKCS7-aligned
        self.assertEqual(len(ciphertext) % 16, 0)

    def test_inbound_hash_matches_doc_style(self):
        payload = (
            '{"amount":100.0,"transactionStatus":"I","fpTransactionId":"FP00187352S",'
            '"typeOfTransaction":"CDC","bcLoginId":"XYZ",'
            '"transactionTimestamp":"2021-07-21 12:23:56",'
            '"errorMessage":"Transaction initiated","remarks":""}'
        )
        secret = '1234567890'
        expected = build_inbound_hash(payload, secret)
        self.assertTrue(verify_inbound_hash(payload, secret, expected))
        self.assertFalse(verify_inbound_hash(payload, secret, 'bad'))

    def test_hash_template_with_semicolon_key(self):
        payload = '{"bcLoginIds":["A"]}'
        secret = '1234567890;'
        h = build_inbound_hash(payload, secret, template='{payload}{secret_key}')
        self.assertTrue(verify_inbound_hash(payload, secret, h, template='{payload}{secret_key}'))

    def test_build_launch_url_hash_route(self):
        url = build_launch_url(
            cms_base_url='https://fpuat.tapits.in',
            login_path='/UberCMSBC/#/login',
            encrypted_data='ABC',
            skey='KEY',
        )
        self.assertEqual(
            url,
            'https://fpuat.tapits.in/UberCMSBC/#/login?data=ABC&skey=KEY',
        )


if __name__ == '__main__':
    unittest.main()
