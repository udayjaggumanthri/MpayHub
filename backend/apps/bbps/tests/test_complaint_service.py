from unittest.mock import patch

from django.test import TestCase

from apps.authentication.models import User
from apps.bbps.models import BbpsComplaint, BbpsPaymentAttempt
from apps.bbps.serializers import ComplaintRegisterSerializer
from apps.bbps.service_flow.complaint_service import register_complaint
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
            'complaint_disposition': 'Transaction successful, Amount Debited but services not received',
        }

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_uses_complaint_desc_first(self, mock_client_cls, _mock_cooling):
        client = mock_client_cls.return_value
        client.register_complaint.return_value = _reg_ok(
            {'complaintRegistrationResp': {'responseCode': '000', 'responseReason': 'SUCCESS', 'complaintId': 'CMP1'}}
        )

        register_complaint(**self.base_kwargs)

        row = BbpsComplaint.objects.filter(user=self.user).order_by('-created_at').first()
        self.assertEqual(row.billavenue_request_id, '0' * 35)

        sent_payload = client.register_complaint.call_args_list[0].args[0]
        self.assertEqual(sent_payload.get('complaintDesc'), self.base_kwargs['complaint_desc'])
        self.assertNotIn('complainDesc', sent_payload)
        self.assertNotIn('complaintType', sent_payload)

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_falls_back_to_complain_desc(self, mock_client_cls, _mock_cooling):
        client = mock_client_cls.return_value
        e1 = BillAvenueClientError(
            'BillAvenue API failed (complaint_register) code=205 {"errorCode":"V5004","errorMessage":"Description missing"}'
        )
        e1.billavenue_request_id = 'E' * 35
        client.register_complaint.side_effect = [
            e1,
            _reg_ok({'complaintRegistrationResp': {'responseCode': '000', 'responseReason': 'SUCCESS', 'complaintId': 'CMP2'}}),
        ]

        register_complaint(**self.base_kwargs)

        self.assertEqual(client.register_complaint.call_count, 2)
        sent_payload = client.register_complaint.call_args_list[1].args[0]
        self.assertEqual(sent_payload.get('complainDesc'), self.base_kwargs['complaint_desc'])

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_tries_combined_alias_payload(self, mock_client_cls, _mock_cooling):
        client = mock_client_cls.return_value
        err = BillAvenueClientError('BillAvenue API failed (complaint_register) code=205 {"errorCode":"V5004","errorMessage":"Description missing"}')
        err.billavenue_request_id = 'M' * 35
        client.register_complaint.side_effect = [
            err,
            err,
            _reg_ok({'complaintRegistrationResp': {'responseCode': '000', 'responseReason': 'SUCCESS', 'complaintId': 'CMP3'}}),
        ]

        register_complaint(**self.base_kwargs)

        self.assertEqual(client.register_complaint.call_count, 3)
        sent_payload = client.register_complaint.call_args_list[2].args[0]
        self.assertEqual(sent_payload.get('complaintDesc'), self.base_kwargs['complaint_desc'])
        self.assertEqual(sent_payload.get('complainDesc'), self.base_kwargs['complaint_desc'])
        self.assertEqual(sent_payload.get('complaintDescription'), self.base_kwargs['complaint_desc'])

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_non_description_error_fails_fast(self, mock_client_cls, _mock_cooling):
        client = mock_client_cls.return_value
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
        client = mock_client_cls.return_value
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
            'complaint_disposition': 'Transaction successful, Amount Debited but services not received',
        }
        ser = ComplaintRegisterSerializer(data=payload)
        self.assertTrue(ser.is_valid(), ser.errors)

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
        client = mock_client_cls.return_value
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
        client = mock_client_cls.return_value
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
