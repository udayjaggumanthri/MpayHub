from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from apps.authentication.models import User
from apps.bbps.models import BbpsComplaint, BbpsPaymentAttempt
from apps.bbps.serializers import ComplaintRegisterSerializer
from apps.bbps.service_flow.complaint_service import (
    _canonical_billavenue_complaint_disposition,
    _nearby_open_complaint_hints,
    register_complaint,
)
from apps.core.exceptions import TransactionFailed
from apps.integrations.billavenue.errors import BillAvenueClientError


def _reg_ok(resp_dict, rid=None):
    """BBPSClient.register_complaint returns (normalized, billavenue_request_id)."""
    return resp_dict, (rid or ('0' * 35))


class ComplaintServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9111111111',
            email='complaint-tests@example.com',
            password='secret123',
        )
        self.base_kwargs = {
            'user': self.user,
            'txn_ref_id': 'CC015135BAAA92192259',
            'complaint_desc': 'Service not received after successful payment',
            'complaint_disposition': 'Transaction Successful, Amount Debited but services not received',
        }
        BbpsPaymentAttempt.objects.create(
            user=self.user,
            idempotency_key='complaint-test-base-attempt',
            txn_ref_id=self.base_kwargs['txn_ref_id'],
            request_id='0' * 35,
            status='SUCCESS',
            biller_id='TESTBILLER01',
            request_payload={'agent_id': 'CC01TESTAGENT0001'},
        )

    def _mock_client_with_status(self, mock_client_cls, txn_ref_id):
        client = mock_client_cls.return_value
        client.transaction_status.return_value = [{'txnRefId': txn_ref_id}]
        return client

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_uses_complaint_desc_first(self, mock_client_cls, _mock_cooling):
        client = self._mock_client_with_status(mock_client_cls, self.base_kwargs['txn_ref_id'])
        client.register_complaint.return_value = _reg_ok(
            {'complaintRegistrationResp': {'responseCode': '000', 'responseReason': 'SUCCESS', 'complaintId': 'CMP1'}}
        )

        register_complaint(**self.base_kwargs)

        row = BbpsComplaint.objects.filter(user=self.user).order_by('-created_at').first()
        self.assertEqual(row.billavenue_request_id, '0' * 35)

        sent_payload = client.register_complaint.call_args_list[0].args[0]
        self.assertEqual(sent_payload.get('complaintDesc'), self.base_kwargs['complaint_desc'])
        self.assertNotIn('complaintType', sent_payload)

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_falls_back_to_complain_desc(self, mock_client_cls, _mock_cooling):
        client = self._mock_client_with_status(mock_client_cls, self.base_kwargs['txn_ref_id'])
        e1 = BillAvenueClientError(
            'BillAvenue API failed (complaint_register) code=205 {"errorCode":"V5004","errorMessage":"Description missing"}'
        )
        e1.billavenue_request_id = 'E' * 35
        client.register_complaint.side_effect = [
            e1,
            e1,
            e1,
            _reg_ok({'complaintRegistrationResp': {'responseCode': '000', 'responseReason': 'SUCCESS', 'complaintId': 'CMP2'}}),
        ]

        register_complaint(**self.base_kwargs)

        self.assertEqual(client.register_complaint.call_count, 4)
        sent_payload = client.register_complaint.call_args_list[3].args[0]
        self.assertEqual(sent_payload.get('complainDesc'), self.base_kwargs['complaint_desc'])

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_tries_combined_alias_payload(self, mock_client_cls, _mock_cooling):
        client = self._mock_client_with_status(mock_client_cls, self.base_kwargs['txn_ref_id'])
        err = BillAvenueClientError('BillAvenue API failed (complaint_register) code=205 {"errorCode":"V5004","errorMessage":"Description missing"}')
        err.billavenue_request_id = 'M' * 35
        client.register_complaint.side_effect = [
            err,
            err,
            err,
            err,
            _reg_ok({'complaintRegistrationResp': {'responseCode': '000', 'responseReason': 'SUCCESS', 'complaintId': 'CMP3'}}),
        ]

        register_complaint(**self.base_kwargs)

        self.assertEqual(client.register_complaint.call_count, 5)
        sent_payload = client.register_complaint.call_args_list[4].args[0]
        self.assertEqual(sent_payload.get('complaintDesc'), self.base_kwargs['complaint_desc'])
        self.assertEqual(sent_payload.get('complainDesc'), self.base_kwargs['complaint_desc'])
        self.assertEqual(sent_payload.get('complaintDescription'), self.base_kwargs['complaint_desc'])

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_non_description_error_fails_fast(self, mock_client_cls, _mock_cooling):
        client = self._mock_client_with_status(mock_client_cls, self.base_kwargs['txn_ref_id'])
        client.register_complaint.side_effect = BillAvenueClientError(
            'BillAvenue API failed (complaint_register) code=205 {"errorCode":"V5001","errorMessage":"Invalid txnRefId format"}'
        )

        with self.assertRaises(BillAvenueClientError):
            register_complaint(**self.base_kwargs)

        self.assertEqual(client.register_complaint.call_count, 1)

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_maps_complaint_response_fields(self, mock_client_cls, _mock_cooling):
        """Provider may return complaintResponse* fields (BBPS 2.8.7 style) instead of responseCode/responseReason."""
        client = self._mock_client_with_status(mock_client_cls, self.base_kwargs['txn_ref_id'])
        rid = 'P' * 35
        client.register_complaint.return_value = _reg_ok(
            {
                'complaintRegistrationResp': {
                    'complaintId': 'CC0125122209187',
                    'complaintStatus': 'Assigned',
                    'complaintResponseCode': '000',
                    'complaintResponseReason': 'SUCCESS',
                }
            },
            rid,
        )

        row = register_complaint(**self.base_kwargs)

        self.assertEqual(row.complaint_id, 'CC0125122209187')
        self.assertEqual(row.complaint_status, 'Assigned')
        self.assertEqual(row.response_code, '000')
        self.assertEqual(row.response_reason, 'SUCCESS')
        self.assertEqual(row.billavenue_request_id, rid)

    def test_serializer_accepts_internal_service_id_length(self):
        payload = {
            'txn_ref_id': 'PMBBPS20260505153803C75612',
            'complaint_desc': 'Service not received',
            'complaint_disposition': 'Transaction Successful, Amount Debited but services not received',
        }
        ser = ComplaintRegisterSerializer(data=payload)
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_serializer_accepts_complain_desc_alias(self):
        ser = ComplaintRegisterSerializer(
            data={
                'txn_ref_id': 'CC015135BAAA92192259',
                'complain_desc': 'Testing Complaint registration through API',
                'complaint_disposition': 'Transaction Successful, Amount Debited but services not received',
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data['complaint_desc'], 'Testing Complaint registration through API')

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_blocks_duplicate_open_case(self, mock_client_cls, _mock_cooling):
        BbpsComplaint.objects.create(
            user=self.user,
            txn_ref_id=self.base_kwargs['txn_ref_id'],
            complaint_id='CMP-DUP-1',
            complaint_desc='Already raised',
            complaint_disposition=self.base_kwargs['complaint_disposition'],
            complaint_status='ASSIGNED',
            response_code='000',
            response_reason='SUCCESS',
            raw_payload={},
        )
        with self.assertRaises(TransactionFailed) as exc:
            register_complaint(**self.base_kwargs)
        self.assertIn('Duplicate complaint already exists', str(exc.exception))
        mock_client_cls.return_value.register_complaint.assert_not_called()

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_blocks_when_open_complaint_other_disposition(self, mock_client_cls, _mock_cooling):
        BbpsComplaint.objects.create(
            user=self.user,
            txn_ref_id=self.base_kwargs['txn_ref_id'],
            complaint_id='CMP-OTHER-DISP',
            complaint_desc='First case',
            complaint_disposition='Duplicate Payment',
            complaint_status='ASSIGNED',
            response_code='000',
            response_reason='SUCCESS',
            raw_payload={},
        )
        kwargs = {**self.base_kwargs, 'complaint_disposition': 'Erroneously paid in wrong account'}
        with self.assertRaises(TransactionFailed) as exc:
            register_complaint(**kwargs)
        self.assertIn('this transaction already has an open complaint', str(exc.exception).lower())
        self.assertIn('CMP-OTHER-DISP', str(exc.exception))
        mock_client_cls.return_value.register_complaint.assert_not_called()

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_maps_pmbbps_via_nested_txnref_in_payload(self, mock_client_cls, _mock_cooling):
        """My Bills service_id (PMBBPS…) must not be sent upstream; recover CC from stored pay response."""
        sid = 'PMBBPS20260505153803C75612'
        BbpsPaymentAttempt.objects.create(
            user=self.user,
            idempotency_key='idem-complaint-pmbbps-nested-1',
            service_id=sid,
            txn_ref_id='',
            status='SUCCESS',
            response_payload={
                'ExtBillPayResponse': {'billPayResponse': {'txnRefId': 'CC_FROM_PAYLOAD_0001'}}
            },
        )
        client = self._mock_client_with_status(mock_client_cls, 'CC_FROM_PAYLOAD_0001')
        client.register_complaint.return_value = _reg_ok(
            {'complaintRegistrationResp': {'responseCode': '000', 'responseReason': 'SUCCESS', 'complaintId': 'CMP-P'}}
        )

        register_complaint(
            user=self.user,
            txn_ref_id=sid,
            complaint_desc='Issue with bill',
            complaint_disposition=self.base_kwargs['complaint_disposition'],
        )

        sent = client.register_complaint.call_args_list[0].args[0]
        self.assertEqual(sent.get('txnRefId'), 'CC_FROM_PAYLOAD_0001')

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_pmbbps_without_upstream_txn_raises(self, mock_client_cls, _mock_cooling):
        sid = 'PMBBPS20260505153803C75699'
        BbpsPaymentAttempt.objects.create(
            user=self.user,
            idempotency_key='idem-complaint-pmbbps-empty-1',
            service_id=sid,
            txn_ref_id='',
            status='FAILED',
            response_payload={},
        )
        with self.assertRaises(TransactionFailed) as exc:
            register_complaint(
                user=self.user,
                txn_ref_id=sid,
                complaint_desc='Issue',
                complaint_disposition=self.base_kwargs['complaint_disposition'],
            )
        self.assertIn('Could not resolve', str(exc.exception))
        mock_client_cls.return_value.register_complaint.assert_not_called()

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_maps_bill_pay_request_id_to_txn(self, mock_client_cls, _mock_cooling):
        rid = '0' * 35
        BbpsPaymentAttempt.objects.create(
            user=self.user,
            idempotency_key='idem-complaint-reqid-1',
            service_id='PMBBPS20260505153803REQID',
            request_id=rid,
            txn_ref_id='CC_VIA_REQUEST_ID_LOOKUP',
            status='SUCCESS',
            response_payload={},
        )
        client = self._mock_client_with_status(mock_client_cls, 'CC_VIA_REQUEST_ID_LOOKUP')
        client.register_complaint.return_value = _reg_ok(
            {'complaintRegistrationResp': {'responseCode': '000', 'responseReason': 'SUCCESS', 'complaintId': 'CMP-R'}}
        )

        register_complaint(
            user=self.user,
            txn_ref_id=rid,
            complaint_desc='Issue',
            complaint_disposition=self.base_kwargs['complaint_disposition'],
        )

        sent = client.register_complaint.call_args_list[0].args[0]
        self.assertEqual(sent.get('txnRefId'), 'CC_VIA_REQUEST_ID_LOOKUP')
        self.assertEqual(sent.get('paymentRefId'), rid)


class ComplaintNearbyHintTests(TestCase):
    def test_nearby_open_complaint_hint_for_sibling_txn(self):
        user = User.objects.create_user(phone='9222222222', email='nearby@example.com', password='secret123')
        BbpsComplaint.objects.create(
            user=user,
            txn_ref_id='CC016137BAAG00059241',
            complaint_id='CC0126141551851',
            complaint_desc='Open',
            complaint_disposition='Transaction Successful, Amount Debited but services not received',
            complaint_status='ASSIGNED',
            response_code='000',
            response_reason='SUCCESS',
            raw_payload={},
        )
        hint = _nearby_open_complaint_hints(user=user, upstream_txn_ref_id='CC016137BAAG00059242')
        self.assertIn('59241', hint)
        self.assertIn('CC0126141551851', hint)


class ComplaintDispositionCanonicalTests(SimpleTestCase):
    def test_legacy_lowercase_successful_maps_to_official(self):
        self.assertEqual(
            _canonical_billavenue_complaint_disposition(
                'Transaction successful, Amount Debited but services not received'
            ),
            'Transaction Successful, Amount Debited but services not received',
        )

    def test_viii_trailing_period_maps_to_xml_canonical(self):
        self.assertEqual(
            _canonical_billavenue_complaint_disposition(
                'Bill Paid but Amount not adjusted or still showing due amount.'
            ),
            'Bill Paid but Amount not adjusted or still showing due amount',
        )

    def test_payment_info_alias_maps(self):
        self.assertEqual(
            _canonical_billavenue_complaint_disposition('Payment info not received / delayed from biller'),
            'Payment information not received from Biller or Delay in receiving payment information from the Biller.',
        )
