"""Fetch routing for MDM NOT_SUPPORTED / adhoc billers."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.bbps.catalog.persist_biller import persist_biller_from_mdm_row
from apps.bbps.service_flow.fetch_service import fetch_bill_with_cache
from apps.integrations.billavenue.registry import activate_billavenue_config, get_or_create_billavenue_mode_row

User = get_user_model()


class FetchNotSupportedRoutingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='919900112233',
            email='fetch_ns@example.com',
            password='pass12345',
            role='Retailer',
            user_id='FETCHNS01',
            first_name='F',
            last_name='N',
        )
        prod = get_or_create_billavenue_mode_row('prod')
        prod.enabled = True
        prod.base_url = 'https://api.billavenue.com'
        prod.save()
        activate_billavenue_config(prod)
        persist_biller_from_mdm_row(
            {
                'billerId': 'ATPOST000NAT01',
                'billerName': 'Airtel Postpaid',
                'billerCategory': 'Mobile Postpaid',
                'billerStatus': 'ACTIVE',
                'billerAdhoc': 'true',
                'billerFetchRequiremet': 'NOT_SUPPORTED',
                'billerSupportBillValidation': 'MANDATORY',
            },
            environment='prod',
        )

    @patch('apps.bbps.service_flow.fetch_service.validate_bill_account')
    @patch('apps.bbps.service_flow.fetch_service.BBPSClient')
    def test_not_supported_skips_bill_fetch_and_validates(self, mock_client_cls, mock_validate):
        mock_validate.return_value = {'skipped': False, 'response_code': '000', 'response': {'responseCode': '000'}}
        out = fetch_bill_with_cache(
            user=self.user,
            biller_id='ATPOST000NAT01',
            customer_info={'customerMobile': '9652488158'},
            input_params=[{'paramName': 'Mobile Number', 'paramValue': '9652488158'}],
            agent_device_info={'initChannel': 'AGT', 'ip': '127.0.0.1'},
            agent_id='CC01CC01513515340681',
            biller_adhoc=True,
        )
        mock_client_cls.assert_not_called()
        mock_validate.assert_called_once()
        result = out['bill_result']
        self.assertEqual(result['flow'], 'adhoc_validate')
        self.assertTrue(result['biller_adhoc'])
        self.assertEqual(result['amount'], 0)
        self.assertTrue(out['fetch_session'].request_id.startswith('VAL'))
