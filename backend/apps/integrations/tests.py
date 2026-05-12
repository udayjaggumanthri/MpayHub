from django.test import SimpleTestCase, TestCase

from apps.integrations.bbps_client import (
    _normalize_bbps_payment_mode,
    extract_biller_response_dict,
    resolve_remitter_display_name,
)
from apps.integrations.billavenue.crypto import decrypt_payload, encrypt_payload
from apps.integrations.billavenue.envelope import build_encrypted_envelope
from apps.integrations.billavenue.request_id import generate_billavenue_request_id
from apps.integrations.billavenue.parsers import extract_element_outer_xml_from_plaintext
from apps.integrations.billavenue.xml_request import (
    build_bill_fetch_plain_xml,
    build_biller_info_plain_xml,
    build_bill_pay_plain_xml,
    build_plan_pull_plain_xml,
)
from apps.integrations.billavenue.client import BillAvenueClient


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


class BillAvenueBillFetchXmlTests(TestCase):
    def test_bill_fetch_xml_emits_all_input_params(self):
        xml = build_bill_fetch_plain_xml(
            {
                'agentId': 'AG01',
                'billerId': 'B1',
                'customerInfo': {'customerMobile': '9999999999'},
                'agentDeviceInfo': {'initChannel': 'AGT', 'ip': '127.0.0.1'},
                'inputParams': {
                    'input': [
                        {'paramName': 'CustomerId', 'paramValue': 'C1'},
                        {'paramName': 'SubDivision', 'paramValue': 'SDO1'},
                    ]
                },
            }
        )
        self.assertIn('<paramName>CustomerId</paramName>', xml)
        self.assertIn('<paramValue>C1</paramValue>', xml)
        self.assertIn('<paramName>SubDivision</paramName>', xml)
        self.assertIn('<paramValue>SDO1</paramValue>', xml)


class BillAvenueXmlRequestTests(TestCase):
    def test_biller_info_xml_empty_payload(self):
        xml = build_biller_info_plain_xml({})
        self.assertIn('billerInfoRequest', xml)
        self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', xml)
        self.assertNotIn('agentId', xml)

    def test_biller_info_xml_agent_and_ids(self):
        xml = build_biller_info_plain_xml({'agentId': 'AGT01', 'billerId': ['A', 'B']})
        self.assertIn('<agentId>AGT01</agentId>', xml)
        self.assertIn('<billerId>A</billerId>', xml)
        self.assertIn('<billerId>B</billerId>', xml)

    def test_plan_pull_xml_list(self):
        xml = build_plan_pull_plain_xml({'billerId': ['X1', 'X2']})
        self.assertIn('planDetailsRequest', xml)
        self.assertIn('<billerId>X1</billerId>', xml)
        self.assertIn('<billerId>X2</billerId>', xml)

    def test_plan_pull_xml_scalar(self):
        xml = build_plan_pull_plain_xml({'billerId': 'OTME00005XXZ43'})
        self.assertIn('<billerId>OTME00005XXZ43</billerId>', xml)


class BbpsBillAvenueHardeningTests(TestCase):
    def test_extract_biller_response_direct(self):
        raw = {'billerResponse': {'customerName': 'Alice', 'billAmount': '100'}}
        self.assertEqual(extract_biller_response_dict(raw).get('customerName'), 'Alice')

    def test_extract_biller_response_nested_bill_fetch(self):
        raw = {
            'billFetchResponse': {
                'billerResponse': {'consumerName': 'Bob'},
            }
        }
        self.assertEqual(extract_biller_response_dict(raw).get('consumerName'), 'Bob')

    def test_extract_biller_response_ext_wrapper(self):
        raw = {
            'ExtBillFetchResponse': {
                'billFetchResponse': {'billerResponse': {'customerName': 'Carol'}},
            }
        }
        self.assertEqual(extract_biller_response_dict(raw).get('customerName'), 'Carol')

    def test_extract_prefers_nested_biller_response_over_shallow_stub(self):
        raw = {
            'billerResponse': {'billAmount': '100000'},
            'billFetchResponse': {
                'billerResponse': {
                    'billAmount': '100000',
                    'customerName': 'Full',
                    'additionalInfo': {'info': [{'infoName': 'Plan', 'infoValue': 'P1'}]},
                }
            },
        }
        br = extract_biller_response_dict(raw)
        self.assertEqual(br.get('customerName'), 'Full')
        self.assertIn('additionalInfo', br)

    def test_extract_case_insensitive_bill_fetch_keys(self):
        raw = {'BillFetchResponse': {'BillerResponse': {'customerName': 'Zed'}}}
        self.assertEqual(extract_biller_response_dict(raw).get('customerName'), 'Zed')

    def test_resolve_remitter_from_biller_response(self):
        name = resolve_remitter_display_name(
            {'biller_response': {'customerName': '  Dee  '}, 'customer_name': 'ignored'}
        )
        self.assertEqual(name, 'Dee')

    def test_resolve_remitter_from_customer_details(self):
        name = resolve_remitter_display_name(
            {'customer_details': {'Customer Name': 'Eve'}, 'biller_response': {}}
        )
        self.assertEqual(name, 'Eve')

    def test_resolve_remitter_uses_biller_response_before_top_level(self):
        name = resolve_remitter_display_name(
            {
                'biller_response': {'customerName': 'FromBill'},
                'remitter_name': 'Explicit',
            }
        )
        self.assertEqual(name, 'FromBill')

    def test_resolve_remitter_falls_back_to_remitter_name(self):
        name = resolve_remitter_display_name(
            {'biller_response': {}, 'remitter_name': 'Explicit', 'customer_name': ''}
        )
        self.assertEqual(name, 'Explicit')

    def test_normalize_bbps_payment_mode_table(self):
        self.assertEqual(_normalize_bbps_payment_mode('cash'), 'Cash')
        self.assertEqual(_normalize_bbps_payment_mode('internet banking'), 'Internet Banking')
        self.assertEqual(_normalize_bbps_payment_mode('Bharat QR'), 'Bharat QR')
        self.assertEqual(_normalize_bbps_payment_mode('prepaid card'), 'Prepaid Card')

    def test_build_bill_pay_plain_xml_payment_ref_and_remitter(self):
        xml = build_bill_pay_plain_xml(
            {
                'paymentRefId': 'CORR123',
                'agentId': 'AG01',
                'customerInfo': {'customerMobile': '9999999999', 'customerName': 'Shop Owner'},
                'billerId': 'BILLER1',
                'inputParams': {'input': [{'paramName': 'a', 'paramValue': 'b'}]},
                'amountInfo': {'amount': '50000', 'currency': '356', 'custConvFee': '0'},
                'paymentMethod': {'paymentMode': 'Cash', 'quickPay': 'N', 'splitPay': 'N'},
                'paymentInfo': {
                    'info': [
                        {'infoName': 'Remitter Name', 'infoValue': 'Shop Owner'},
                        {'infoName': 'PaymentRefId', 'infoValue': 'CORR123'},
                        {'infoName': 'Payment Account Info', 'infoValue': 'CORR123|CORR123'},
                        {'infoName': 'Payment mode', 'infoValue': 'Cash'},
                    ]
                },
            }
        )
        self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', xml)
        idx_ref = xml.index('<paymentRefId>CORR123</paymentRefId>')
        idx_biller = xml.index('<billerId>BILLER1</billerId>')
        self.assertLess(idx_ref, idx_biller)
        self.assertIn('<customerName>Shop Owner</customerName>', xml)
        self.assertIn('<infoName>Remitter Name</infoName>', xml)
        self.assertIn('<infoValue>Shop Owner</infoValue>', xml)

    def test_build_bill_pay_plain_xml_biller_response_nested_additional_info(self):
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
                'billerResponse': {
                    'billAmount': '100000',
                    'customerName': 'Cust',
                    'additionalInfo': {
                        'info': [
                            {'infoName': 'Minimum Amount Due', 'infoValue': '50000'},
                            {'infoName': 'Current Outstanding Amount', 'infoValue': '100000'},
                        ]
                    },
                },
                'amountInfo': {'amount': '100000', 'currency': '356', 'custConvFee': '0'},
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
        self.assertIn('<billerResponse>', xml)
        self.assertIn('<additionalInfo>', xml)
        self.assertIn('<infoName>Minimum Amount Due</infoName>', xml)
        self.assertIn('<infoValue>50000</infoValue>', xml)
        self.assertIn('<billAmount>100000</billAmount>', xml)

    def test_bill_pay_xml_biller_response_emits_empty_scalar_leaf(self):
        xml = build_bill_pay_plain_xml(
            {
                'paymentRefId': 'CORR1',
                'requestId': 'CORR1',
                'agentId': 'AG01',
                'billerAdhoc': False,
                'agentDeviceInfo': {'initChannel': 'AGT'},
                'customerInfo': {'customerMobile': '9999999999', 'customerName': 'Payer'},
                'billerId': 'B1',
                'inputParams': {'input': []},
                'billerResponse': {'dueDate': '', 'billAmount': '100000'},
                'amountInfo': {'amount': '100000', 'currency': '356', 'custConvFee': '0'},
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
        self.assertIn('<dueDate></dueDate>', xml)

    def test_safe_timeout_tuple_clamps_configured_values(self):
        client = BillAvenueClient.__new__(BillAvenueClient)
        client.config = type(
            'Cfg',
            (),
            {
                'connect_timeout_seconds': 999,
                'read_timeout_seconds': 999,
            },
        )()
        self.assertEqual(client._safe_timeout_tuple(), (10, 25))


class BillAvenueSnapshotXmlTests(SimpleTestCase):
    """No DB — parser / XML helpers for fetch→pay billerResponse echo (E211)."""

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
