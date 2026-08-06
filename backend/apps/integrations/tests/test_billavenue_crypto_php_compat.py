"""BillAvenue crypto aligned with CCAvenue/BillAvenue PHP samples (md5 key + fixed IV + hex out)."""

from django.test import SimpleTestCase

from apps.integrations.billavenue.crypto import (
    BILLAVENUE_STANDARD_IV_HEX,
    decrypt_payload,
    encrypt_payload,
)


class BillAvenuePhpCompatTests(SimpleTestCase):
    def test_standard_iv_used_when_iv_label_typo(self):
        key = 'BE8B7422B94DEC42CF4DE4DABB450A7F'
        plain = 'atulpandey'
        enc = encrypt_payload(
            plain,
            working_key=key,
            iv='IV',
            key_derivation='md5',
            output_encoding='hex',
        )
        dec = decrypt_payload(
            enc,
            working_key=key,
            iv=BILLAVENUE_STANDARD_IV_HEX,
            key_derivation='md5',
            input_encoding='hex',
        )
        self.assertEqual(dec, plain)

    def test_md5_hex_roundtrip(self):
        key = 'atul'
        plain = 'atulpandey'
        enc = encrypt_payload(
            plain,
            working_key=key,
            iv=BILLAVENUE_STANDARD_IV_HEX,
            key_derivation='md5',
            output_encoding='hex',
        )
        self.assertTrue(enc and all(c in '0123456789abcdefABCDEF' for c in enc))
        dec = decrypt_payload(
            enc,
            working_key=key,
            iv=BILLAVENUE_STANDARD_IV_HEX,
            key_derivation='md5',
            input_encoding='hex',
        )
        self.assertEqual(dec, plain)
