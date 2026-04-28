from django.test import TestCase

from apps.integrations.billavenue.crypto import decrypt_payload, encrypt_payload
from apps.integrations.billavenue.envelope import build_encrypted_envelope
from apps.integrations.billavenue.request_id import generate_billavenue_request_id


class BillAvenueCryptoTests(TestCase):
    def test_crypto_roundtrip(self):
        plain = '{"hello":"world"}'
        enc = encrypt_payload(plain, working_key='1234567890abcdef', iv='abcdef1234567890')
        out = decrypt_payload(enc, working_key='1234567890abcdef', iv='abcdef1234567890')
        self.assertEqual(out, plain)

    def test_request_id_format_and_length(self):
        rid = generate_billavenue_request_id()
        self.assertEqual(len(rid), 35)
        self.assertTrue(rid.isalnum())

    def test_envelope_contains_required_keys(self):
        env = build_encrypted_envelope(
            payload_text='{}',
            access_code='acc',
            institute_id='inst',
            ver='1.0',
            working_key='1234567890abcdef',
            iv='abcdef1234567890',
        )
        self.assertIn('accessCode', env)
        self.assertIn('requestId', env)
        self.assertIn('encRequest', env)
        self.assertIn('ver', env)
        self.assertIn('instituteId', env)
