from django.test import SimpleTestCase

from apps.integrations.bbps_client import (
    coerce_bbps_info_rows,
    extract_biller_response_dict,
    normalize_additional_info_rows,
)
from apps.integrations.billavenue.parsers import extract_element_outer_xml_from_plaintext
from apps.integrations.billavenue.xml_request import build_bill_pay_plain_xml


class BillAvenueSnapshotXmlTests(SimpleTestCase):
    """Fetch→pay snapshot echo helpers (E211 billerResponse / E212 additionalInfo)."""

    def test_extract_biller_response_ignores_internal_xml_snapshot_key(self):
        raw = {
            '__mpayhub_biller_response_xml': '<billerResponse><billAmount>1</billAmount></billerResponse>',
            'billFetchResponse': {'billerResponse': {'customerName': 'Keep'}},
        }
        br = extract_biller_response_dict(raw)
        self.assertEqual(br.get('customerName'), 'Keep')
        self.assertNotIn('__mpayhub', str(br))

    def test_extract_element_outer_xml_from_plaintext_nested(self):
        plain = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<billFetchResponse>'
            '<responseCode>000</responseCode>'
            '<billerResponse><billAmount>100500</billAmount><customerName>OTME</customerName></billerResponse>'
            '</billFetchResponse>'
        )
        frag = extract_element_outer_xml_from_plaintext(plain, 'billerResponse')
        self.assertIn('<billAmount>100500</billAmount>', frag)
        self.assertIn('<customerName>OTME</customerName>', frag)

    def test_extract_root_additional_info_skips_nested_under_biller_response(self):
        plain = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<billFetchResponse>'
            '<billerResponse>'
            '<billAmount>100</billAmount>'
            '<additionalInfo><info><infoName>Nested</infoName><infoValue>bad</infoValue></info></additionalInfo>'
            '</billerResponse>'
            '<additionalInfo><info><infoName>Minimum Amount Due</infoName><infoValue>3151.99</infoValue></info>'
            '<info><infoName>Maximum Permissible Amount</infoName><infoValue>55400.53</infoValue></info>'
            '</additionalInfo>'
            '</billFetchResponse>'
        )
        frag = extract_element_outer_xml_from_plaintext(
            plain, 'additionalInfo', not_under_local_names=frozenset({'billerresponse'})
        )
        self.assertIn('Minimum Amount Due', frag)
        self.assertIn('3151.99', frag)
        self.assertNotIn('Nested', frag)
        self.assertNotIn('>bad<', frag)

    def test_build_bill_pay_prefers_additional_info_xml_literal(self):
        frag = (
            '<additionalInfo><info><infoName>Minimum Amount Due</infoName>'
            '<infoValue>3151.99</infoValue></info></additionalInfo>'
        )
        xml = build_bill_pay_plain_xml(
            {
                'paymentRefId': 'CORR1',
                'requestId': 'CORR1',
                'agentId': 'AG01',
                'billerAdhoc': True,
                'agentDeviceInfo': {'initChannel': 'AGT'},
                'customerInfo': {'customerMobile': '9999999999', 'customerName': 'Payer'},
                'billerId': 'CANA00000NATDO',
                'inputParams': {'input': [{'paramName': 'a', 'paramValue': '1'}]},
                'billerResponse': {'billAmount': '3785528', 'customerName': 'Cust'},
                'additionalInfoXml': frag,
                'additionalInfo': {
                    'info': [{'infoName': 'Minimum Amount Due', 'infoValue': 'WRONG'}],
                },
                'amountInfo': {'amount': '300000', 'currency': '356', 'custConvFee': '0'},
                'paymentMethod': {'paymentMode': 'Cash', 'quickPay': 'N', 'splitPay': 'N'},
                'paymentInfo': {
                    'info': [
                        {'infoName': 'Remitter Name', 'infoValue': 'Payer'},
                        {'infoName': 'PaymentRefId', 'infoValue': 'CORR1'},
                        {'infoName': 'Payment Account Info', 'infoValue': 'CORR1|CORR1'},
                        {'infoName': 'Payment mode', 'infoValue': 'Cash'},
                    ]
                },
            }
        )
        self.assertIn('3151.99', xml)
        self.assertNotIn('WRONG', xml)
        self.assertIn('<amount>300000</amount>', xml)

    def test_coerce_single_additional_info_dict(self):
        rows = coerce_bbps_info_rows({'infoName': 'Due amount', 'infoValue': '376.0'})
        self.assertEqual(len(rows), 1)
        norm = normalize_additional_info_rows(rows)
        self.assertEqual(norm[0]['infoValue'], '376.0')

    def test_build_bill_pay_prefers_biller_response_xml_literal(self):
        frag = (
            '<billerResponse><billAmount>100500</billAmount>'
            '<customerName>FromXml</customerName></billerResponse>'
        )
        xml = build_bill_pay_plain_xml(
            {
                'paymentRefId': 'CORR1',
                'requestId': 'CORR1',
                'agentId': 'AG01',
                'billerAdhoc': False,
                'agentDeviceInfo': {'initChannel': 'AGT'},
                'customerInfo': {'customerMobile': '9999999999', 'customerName': 'Payer'},
                'billerId': 'OTME00005XXZ43',
                'inputParams': {'input': [{'paramName': 'a', 'paramValue': '1'}]},
                'billerResponseXml': frag,
                'billerResponse': {'billAmount': '999999', 'customerName': 'Wrong'},
                'amountInfo': {'amount': '100500', 'currency': '356', 'custConvFee': '0'},
                'paymentMethod': {'paymentMode': 'Cash', 'quickPay': 'N', 'splitPay': 'N'},
                'paymentInfo': {
                    'info': [
                        {'infoName': 'Remitter Name', 'infoValue': 'Payer'},
                        {'infoName': 'PaymentRefId', 'infoValue': 'CORR1'},
                        {'infoName': 'Payment Account Info', 'infoValue': 'CORR1|CORR1'},
                        {'infoName': 'Payment mode', 'infoValue': 'Cash'},
                    ]
                },
            }
        )
        self.assertIn('<billAmount>100500</billAmount>', xml)
        self.assertIn('<customerName>FromXml</customerName>', xml)
        self.assertNotIn('Wrong', xml)
