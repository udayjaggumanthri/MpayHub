"""Ensure plaintext XML gateway errors are parsed (not left as raw-only PARSE)."""

from django.test import SimpleTestCase

from apps.integrations.billavenue.client import _retry_parse_if_only_raw
from apps.integrations.billavenue.parsers import extract_response_code, parse_payload_text


class PlaintextXmlRecoveryTests(SimpleTestCase):
    def test_parse_biller_info_xml_error_body(self):
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<billerInfoResponse>'
            '<responseCode>202</responseCode>'
            '<errorInfo><error>'
            '<errorCode>DE202</errorCode>'
            '<errorMessage>Request size exceeded</errorMessage>'
            '</error></errorInfo>'
            '</billerInfoResponse>'
        )
        parsed = parse_payload_text(xml)
        self.assertEqual(extract_response_code(parsed), '202')

    def test_raw_only_xml_is_rescued(self):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<billerInfoResponse><responseCode>001</responseCode></billerInfoResponse>'
        )
        rescued = _retry_parse_if_only_raw({'raw': xml}, xml)
        self.assertNotEqual(set(rescued.keys()), {'raw'})
        self.assertEqual(extract_response_code(rescued), '001')

    def test_raw_only_without_parse_misses_code(self):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<billerInfoResponse><responseCode>202</responseCode></billerInfoResponse>'
        )
        self.assertEqual(extract_response_code({'raw': xml}), '')

    def test_xml_with_bracket_fragment_not_stolen_by_json(self):
        """Regression: opportunistic JSON must not return ``[12]`` from inside MDM XML."""
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<billerInfoResponse>'
            '<responseCode>000</responseCode>'
            '<biller>'
            '<billerId>ACKO00000NATJ1</billerId>'
            '<billerName>Acko [12] Insurance</billerName>'
            '<billerCategory>Insurance</billerCategory>'
            '</biller>'
            '</billerInfoResponse>'
        )
        parsed = parse_payload_text(xml)
        self.assertIsInstance(parsed, dict)
        self.assertNotIsInstance(parsed, list)
        self.assertEqual(extract_response_code(parsed), '000')
        self.assertIn('billerInfoResponse', parsed)
