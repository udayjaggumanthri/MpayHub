from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.bbps.models import BbpsBillerInputParam, BbpsBillerMaster
from apps.bbps.service_flow.validation_service import BbpsInputValidationError, validate_biller_inputs
from apps.bbps.views import fetch_bill_view
from apps.users.models import User


class BbpsInputValidationUnitTests(TestCase):
    def setUp(self):
        self.biller = BbpsBillerMaster.objects.create(
            environment='uat',
            biller_id='BSNLPRETEST01',
            biller_name='BSNL Prepaid Test',
            biller_category='Mobile Prepaid',
            biller_status='ACTIVE',
        )
        BbpsBillerInputParam.objects.create(
            biller=self.biller,
            param_name='Mobile Number',
            data_type='NUMERIC',
            is_optional=False,
            min_length=10,
            max_length=10,
            regex=r'^[6-9][0-9]{9}$',
            display_order=1,
        )
        BbpsBillerInputParam.objects.create(
            biller=self.biller,
            param_name='Circle',
            data_type='ALPHANUMERIC',
            is_optional=False,
            min_length=2,
            max_length=40,
            display_order=2,
        )

    def test_exact_name_mismatch_raises_e135(self):
        with self.assertRaises(BbpsInputValidationError) as ctx:
            validate_biller_inputs(
                biller_id='BSNLPRETEST01',
                input_map={'mobile': '9876543210', 'Circle': 'AP'},
            )
        codes = {e['code'] for e in ctx.exception.field_errors}
        self.assertIn('E135', codes)

    def test_min_max_regex_type_failures(self):
        with self.assertRaises(BbpsInputValidationError) as ctx:
            validate_biller_inputs(
                biller_id='BSNLPRETEST01',
                input_map={'Mobile Number': '123', 'Circle': 'AP'},
            )
        by_code = {e['code'] for e in ctx.exception.field_errors}
        self.assertTrue({'VE009', 'VE012'} & by_code or 'VE009' in by_code or 'VE010' in by_code or 'VE011' in by_code or 'VE012' in by_code)

        with self.assertRaises(BbpsInputValidationError) as ctx2:
            validate_biller_inputs(
                biller_id='BSNLPRETEST01',
                input_map={'Mobile Number': 'abcdefghij', 'Circle': 'AP'},
            )
        self.assertTrue(any(e['code'] == 'VE011' for e in ctx2.exception.field_errors))

        with self.assertRaises(BbpsInputValidationError) as ctx3:
            validate_biller_inputs(
                biller_id='BSNLPRETEST01',
                input_map={'Mobile Number': '98765432101234', 'Circle': 'AP'},
            )
        self.assertTrue(any(e['code'] == 'VE010' for e in ctx3.exception.field_errors))

    def test_valid_inputs_return_wire_list(self):
        wire = validate_biller_inputs(
            biller_id='BSNLPRETEST01',
            input_map={'Mobile Number': '9876543210', 'Circle': 'AP'},
        )
        self.assertEqual(
            wire,
            [
                {'paramName': 'Mobile Number', 'paramValue': '9876543210'},
                {'paramName': 'Circle', 'paramValue': 'AP'},
            ],
        )

    def test_hidden_required_param_skipped_when_blank(self):
        BbpsBillerInputParam.objects.create(
            biller=self.biller,
            param_name='Id',
            data_type='ALPHANUMERIC',
            is_optional=False,
            visibility=False,
            min_length=7,
            max_length=16,
            display_order=3,
        )
        with self.assertRaises(BbpsInputValidationError) as ctx:
            validate_biller_inputs(
                biller_id='BSNLPRETEST01',
                input_map={'Mobile Number': '9876543210', 'Circle': 'AP'},
            )
        self.assertTrue(any(e['param'] == 'Id' and e['code'] == 'VE008' for e in ctx.exception.field_errors))

    def test_hidden_optional_param_omitted_when_blank(self):
        BbpsBillerInputParam.objects.create(
            biller=self.biller,
            param_name='Nickname',
            data_type='ALPHANUMERIC',
            is_optional=True,
            visibility=False,
            display_order=3,
        )
        wire = validate_biller_inputs(
            biller_id='BSNLPRETEST01',
            input_map={'Mobile Number': '9876543210', 'Circle': 'AP'},
        )
        names = [r['paramName'] for r in wire]
        self.assertNotIn('Nickname', names)
        self.assertEqual(set(names), {'Mobile Number', 'Circle'})


class BbpsInputValidationApiTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            phone='9999900011',
            email='val.tester@example.com',
            password='TestPass123!',
            first_name='Val',
            last_name='Tester',
        )
        self.biller = BbpsBillerMaster.objects.create(
            environment='uat',
            biller_id='BSNLPRETEST02',
            biller_name='BSNL Prepaid API',
            biller_category='Mobile Prepaid',
            biller_status='ACTIVE',
        )
        BbpsBillerInputParam.objects.create(
            biller=self.biller,
            param_name='Mobile Number',
            data_type='NUMERIC',
            is_optional=False,
            min_length=10,
            max_length=10,
            display_order=1,
        )

    @patch('apps.bbps.views.fetch_bill_with_cache')
    @patch('apps.bbps.catalog.env.active_bbps_environment', return_value='uat')
    def test_fetch_rejects_bad_inputs_without_calling_provider(self, _env, mock_fetch):
        request = self.factory.post(
            '/api/bbps/fetch-bill/',
            {
                'biller_id': 'BSNLPRETEST02',
                'input_params': [{'paramName': 'Wrong Name', 'paramValue': '9876543210'}],
            },
            format='json',
        )
        force_authenticate(request, user=self.user)
        response = fetch_bill_view(request)
        self.assertEqual(response.status_code, 400)
        body = response.data
        self.assertFalse(body.get('success'))
        self.assertEqual(body.get('error', {}).get('code'), 'BBPS_INPUT_INVALID')
        self.assertTrue(body.get('errors'))
        mock_fetch.assert_not_called()
