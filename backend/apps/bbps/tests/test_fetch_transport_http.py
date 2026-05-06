from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.bbps.models import BbpsBillerInputParam, BbpsBillerMaster
from apps.integrations.billavenue.errors import BillAvenueTransportError


class FetchBillTransportHttpTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(phone='9888888888', email='bbps@test.example', password='pass12345')
        self.master = BbpsBillerMaster.objects.create(
            biller_id='HTTPB01',
            biller_name='HTTP Biller',
            biller_category='DTH',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        BbpsBillerInputParam.objects.create(
            biller=self.master,
            param_name='CustomerId',
            data_type='ALPHANUMERIC',
            is_optional=False,
            min_length=1,
            max_length=20,
            regex='',
            visibility=True,
            display_order=1,
        )

    @patch('apps.bbps.views.fetch_bill_with_cache')
    def test_billavenue_timeout_returns_503(self, mock_fetch):
        mock_fetch.side_effect = BillAvenueTransportError(
            'TIMEOUT endpoint=bill_fetch connect=5s read=25s: Read timed out.'
        )
        client = APIClient()
        client.force_authenticate(self.user)
        resp = client.post(
            '/api/bbps/fetch-bill/',
            {
                'biller_id': 'HTTPB01',
                'input_params': [{'paramName': 'CustomerId', 'paramValue': 'abc'}],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 503)
        self.assertIn('timed out', resp.data.get('message', '').lower())
        self.assertEqual(resp.data.get('error', {}).get('code'), 'BBPS_FETCH_TIMEOUT')
        self.assertTrue(resp.data.get('error', {}).get('trace_id'))
        self.assertTrue(resp.data.get('error', {}).get('retryable'))
