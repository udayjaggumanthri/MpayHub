from unittest.mock import patch

from django.test import TestCase

from apps.authentication.models import User
from apps.bbps.models import BbpsComplaint
from apps.bbps.serializers import ComplaintRegisterSerializer
from apps.bbps.service_flow.complaint_service import register_complaint
from apps.core.exceptions import TransactionFailed
from apps.integrations.billavenue.errors import BillAvenueClientError


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

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_uses_complaint_desc_first(self, mock_client_cls, _mock_cooling):
        client = mock_client_cls.return_value
        client.register_complaint.return_value = {
            'complaintRegistrationResp': {'responseCode': '000', 'responseReason': 'SUCCESS', 'complaintId': 'CMP1'}
        }

        register_complaint(**self.base_kwargs)

        sent_payload = client.register_complaint.call_args_list[0].args[0]
        self.assertEqual(sent_payload.get('complaintDesc'), self.base_kwargs['complaint_desc'])
        self.assertNotIn('complainDesc', sent_payload)
        self.assertNotIn('complaintType', sent_payload)

    @patch('apps.bbps.service_flow.complaint_service.enforce_complaint_cooling')
    @patch('apps.bbps.service_flow.complaint_service.BBPSClient')
    def test_register_complaint_falls_back_to_complain_desc(self, mock_client_cls, _mock_cooling):
        client = mock_client_cls.return_value
        client.register_complaint.side_effect = [
            BillAvenueClientError('BillAvenue API failed (complaint_register) code=205 {"errorCode":"V5004","errorMessage":"Description missing"}'),
            {'complaintRegistrationResp': {'responseCode': '000', 'responseReason': 'SUCCESS', 'complaintId': 'CMP2'}},
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
        client.register_complaint.side_effect = [
            err,
            err,
            {'complaintRegistrationResp': {'responseCode': '000', 'responseReason': 'SUCCESS', 'complaintId': 'CMP3'}},
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
        client.register_complaint.return_value = {
            'complaintRegistrationResp': {
                'complaintId': 'CC0125122209187',
                'complaintStatus': 'Assigned',
                'complaintResponseCode': '000',
                'complaintResponseReason': 'SUCCESS',
            }
        }

        row = register_complaint(**self.base_kwargs)

        self.assertEqual(row.complaint_id, 'CC0125122209187')
        self.assertEqual(row.complaint_status, 'Assigned')
        self.assertEqual(row.response_code, '000')
        self.assertEqual(row.response_reason, 'SUCCESS')

    def test_serializer_accepts_internal_service_id_length(self):
        payload = {
            'txn_ref_id': 'PMBBPS20260505153803C75612',
            'complaint_desc': 'Service not received',
            'complaint_disposition': 'Transaction Successful, Amount Debited but services not received',
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
