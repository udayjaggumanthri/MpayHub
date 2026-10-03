"""Tests for BillAvenue remitter compliance (feature-flagged)."""

from decimal import Decimal
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from apps.bbps.error_catalog import resolve_bbps_error
from apps.bbps.service_flow.remitter_compliance import (
    MSG_REMITTER_INCOMPLETE,
    MSG_VPA_INVALID,
    apply_remitter_customer_info,
    build_mode_specific_tags,
    build_remitter_payment_info_rows,
    derive_payment_account_info,
    is_remitter_compliance_enabled,
    merge_payment_info_rows,
    validate_high_value_remitter,
)
from apps.integrations.billavenue.xml_request import build_bill_pay_plain_xml
from apps.bbps.views import _friendly_pay_error_message
from apps.core.exceptions import TransactionFailed
from apps.integrations.bbps_client import BBPSClient, _derive_payment_account_info


class RemitterComplianceUnitTests(SimpleTestCase):
    def test_cash_account_info_is_literal(self):
        val = derive_payment_account_info(
            payment_mode='Cash',
            bill_data={},
            correlation_ref='CORR123',
        )
        self.assertEqual(val, 'Cash Payment')

    def test_legacy_cash_still_uses_pipe_ref(self):
        val = _derive_payment_account_info(
            payment_mode='Cash',
            bill_data={},
            correlation_ref='CORR123',
        )
        self.assertEqual(val, 'CORR123|CORR123')

    def test_upi_requires_at_symbol_in_account_info(self):
        val = derive_payment_account_info(
            payment_mode='UPI',
            bill_data={'vpa': 'user@upi'},
            correlation_ref='R1',
        )
        self.assertEqual(val, 'user@upi')

    def test_card_account_info_pipe_format(self):
        val = derive_payment_account_info(
            payment_mode='Credit Card',
            bill_data={
                'customer_details': {
                    'Card Last4 Digits': '9876',
                    'Card Issuer': 'SBI',
                }
            },
            correlation_ref='R1',
        )
        self.assertEqual(val, '9876|SBI')

    def test_mode_tags_cash_remarks_default(self):
        tags = build_mode_specific_tags(payment_mode='Cash', bill_data={})
        self.assertEqual(tags, [{'infoName': 'Remarks', 'infoValue': 'Received'}])

    def test_merge_upserts_payment_ref_id(self):
        existing = [
            {'infoName': 'Remitter Name', 'infoValue': 'A'},
            {'infoName': 'PaymentRefId', 'infoValue': 'OLD'},
        ]
        required = [
            {'infoName': 'PaymentRefId', 'infoValue': 'NEW'},
            {'infoName': 'Payment Account Info', 'infoValue': 'Cash Payment'},
        ]
        merged = merge_payment_info_rows(existing, required)
        by_name = {r['infoName']: r['infoValue'] for r in merged}
        self.assertEqual(by_name['PaymentRefId'], 'NEW')
        self.assertEqual(by_name['Payment Account Info'], 'Cash Payment')
        self.assertEqual(by_name['Remitter Name'], 'A')

    def test_high_value_payment_info_is_mode_and_account_only(self):
        rows = build_remitter_payment_info_rows(
            remitter_name='RAHUL',
            payment_ref='CORR1',
            payment_mode='Cash',
            bill_data={'customer_info': {'customerPan': 'ABCDE1234F'}},
            amount=Decimal('55000'),
        )
        by_name = {r['infoName']: r['infoValue'] for r in rows}
        self.assertEqual(by_name['Remarks'], 'Received')
        self.assertEqual(by_name['Payment Account Info'], 'Cash Payment')
        self.assertNotIn('PaymentRefId', by_name)
        self.assertNotIn('Remitter Name', by_name)
        self.assertNotIn('PAN', by_name)

    def test_apply_remitter_customer_info_sets_ba_fields(self):
        out = apply_remitter_customer_info(
            {'customerMobile': '9876543210'},
            remitter_name='RAHUL',
            bill_data={'customer_info': {'customerPan': 'ABCDE1234F'}},
        )
        self.assertEqual(out['REMITTER_NAME'], 'RAHUL')
        self.assertEqual(out['customerPan'], 'ABCDE1234F')
        self.assertEqual(out['customerName'], 'RAHUL')

    def test_validate_high_value_requires_identity(self):
        with self.assertRaises(TransactionFailed) as ctx:
            validate_high_value_remitter(
                amount=Decimal('55000'),
                payment_mode='Cash',
                bill_data={'remitter_name': 'RAHUL'},
                remitter_name='RAHUL',
                payment_ref='CORR1',
            )
        self.assertEqual(str(ctx.exception), MSG_REMITTER_INCOMPLETE)

    def test_validate_high_value_rejects_vpa_without_at(self):
        with self.assertRaises(TransactionFailed) as ctx:
            validate_high_value_remitter(
                amount=Decimal('55000'),
                payment_mode='UPI',
                bill_data={
                    'remitter_name': 'RAHUL',
                    'vpa': 'invalidvpa',
                    'customer_info': {'customerPan': 'ABCDE1234F'},
                },
                remitter_name='RAHUL',
                payment_ref='CORR1',
            )
        self.assertEqual(str(ctx.exception), MSG_VPA_INVALID)

    def test_validate_below_50k_noop(self):
        validate_high_value_remitter(
            amount=Decimal('49999'),
            payment_mode='Cash',
            bill_data={},
            remitter_name='',
            payment_ref='',
        )

    def test_flag_helper(self):
        self.assertFalse(is_remitter_compliance_enabled(None))
        cfg = MagicMock(remitter_compliance_enabled=False)
        self.assertFalse(is_remitter_compliance_enabled(cfg))
        cfg.remitter_compliance_enabled = True
        self.assertTrue(is_remitter_compliance_enabled(cfg))


class RemitterPayloadFlagTests(SimpleTestCase):
    def _bill_data(self):
        return {
            'biller_id': 'TESTBILLER01',
            'agent_id': 'AGTTEST001',
            'input_params': [{'paramName': 'a', 'paramValue': '1'}],
            'customer_info': {
                'customerMobile': '9876543210',
                'customerName': 'RAHUL',
                'customerPan': 'ABCDE1234F',
            },
            'remitter_name': 'RAHUL',
            'payment_mode': 'Cash',
            'init_channel': 'AGT',
            'request_id': 'CORR99',
            'agent_device_info': {'initChannel': 'AGT'},
        }

    def test_payload_legacy_when_flag_off(self):
        client = BBPSClient.__new__(BBPSClient)
        client.config = MagicMock(remitter_compliance_enabled=False)
        payload = client._build_bill_payment_payload(
            service_id='SVC1',
            request_id='CORR99',
            amount=Decimal('55000'),
            bill_data=self._bill_data(),
        )
        self.assertEqual(payload.get('paymentRefId'), 'CORR99')
        infos = {r['infoName']: r['infoValue'] for r in payload['paymentInfo']['info']}
        self.assertEqual(infos['Payment Account Info'], 'CORR99|CORR99')
        self.assertNotIn('Remarks', infos)

    def test_payload_compliance_when_flag_on(self):
        client = BBPSClient.__new__(BBPSClient)
        client.config = MagicMock(remitter_compliance_enabled=True)
        payload = client._build_bill_payment_payload(
            service_id='SVC1',
            request_id='CORR99',
            amount=Decimal('55000'),
            bill_data=self._bill_data(),
        )
        self.assertEqual(payload.get('paymentRefId'), 'CORR99')
        infos = {r['infoName']: r['infoValue'] for r in payload['paymentInfo']['info']}
        self.assertEqual(infos['Payment Account Info'], 'Cash Payment')
        self.assertEqual(infos['Remarks'], 'Received')
        self.assertNotIn('PAN', infos)
        self.assertNotIn('PaymentRefId', infos)
        self.assertNotIn('Remitter Name', infos)
        ci = payload['customerInfo']
        self.assertEqual(ci.get('REMITTER_NAME'), 'RAHUL')
        self.assertEqual(ci.get('customerPan'), 'ABCDE1234F')
        xml = build_bill_pay_plain_xml(payload)
        self.assertIn('<REMITTER_NAME>RAHUL</REMITTER_NAME>', xml)
        self.assertIn('<customerPan>ABCDE1234F</customerPan>', xml)
        self.assertIn('<paymentRefId>CORR99</paymentRefId>', xml)
        self.assertNotIn('<infoName>Remitter Name</infoName>', xml)
        self.assertNotIn('<infoName>PaymentRefId</infoName>', xml)

    def test_payload_compliance_strips_identity_from_client_payment_info(self):
        client = BBPSClient.__new__(BBPSClient)
        client.config = MagicMock(remitter_compliance_enabled=True)
        data = self._bill_data()
        data['payment_info'] = {
            'info': [
                {'infoName': 'Remitter Name', 'infoValue': 'RAHUL'},
                {'infoName': 'PaymentRefId', 'infoValue': 'OLD'},
                {'infoName': 'PAN', 'infoValue': 'ABCDE1234F'},
                {'infoName': 'CustomTag', 'infoValue': 'X'},
            ]
        }
        payload = client._build_bill_payment_payload(
            service_id='SVC1',
            request_id='CORR99',
            amount=Decimal('1000'),
            bill_data=data,
        )
        infos = {r['infoName']: r['infoValue'] for r in payload['paymentInfo']['info']}
        self.assertNotIn('PaymentRefId', infos)
        self.assertNotIn('Remitter Name', infos)
        self.assertNotIn('PAN', infos)
        self.assertEqual(infos['CustomTag'], 'X')
        self.assertEqual(infos['Payment Account Info'], 'Cash Payment')
        self.assertEqual(payload['customerInfo'].get('REMITTER_NAME'), 'RAHUL')
        self.assertEqual(payload.get('paymentRefId'), 'CORR99')


class RemitterErrorMappingTests(SimpleTestCase):
    def test_friendly_incomplete_identity(self):
        msg = _friendly_pay_error_message(MSG_REMITTER_INCOMPLETE)
        self.assertIn('PAN or Aadhaar', msg)
        self.assertNotIn('{', msg)

    def test_catalog_incomplete_identity(self):
        info = resolve_bbps_error(MSG_REMITTER_INCOMPLETE, endpoint='bill_pay')
        self.assertEqual(info.app_code, 'BBPS_PAY_REMITTER')
        self.assertIn('PAN or Aadhaar', info.user_message)
        self.assertNotIn('ExtBillPayResponse', info.user_message)

    def test_catalog_vpa(self):
        info = resolve_bbps_error(MSG_VPA_INVALID, endpoint='bill_pay')
        self.assertIn('@', info.user_message)


class RemitterConfigSerializerTests(SimpleTestCase):
    def test_serializer_includes_remitter_flag(self):
        from apps.bbps.serializers import BillAvenueConfigSerializer

        self.assertIn('remitter_compliance_enabled', BillAvenueConfigSerializer.Meta.fields)