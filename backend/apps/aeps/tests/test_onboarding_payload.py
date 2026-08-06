from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch


class OnboardingPayloadMappingTests(SimpleTestCase):
    """Ensure MerchantModelV1 keys match Fingpay Services API Doc."""

    @patch('apps.aeps.services.onboarding.merchant_pin_plain', return_value='4821')
    @patch('apps.aeps.services.onboarding._provider_kyc_defaults', return_value={'gstinNumber': '', 'companyOrShopPan': ''})
    @patch('apps.aeps.services.masters.resolve_state_id', side_effect=lambda v, _s: int(v) if v not in (None, '') else None)
    @patch('apps.aeps.services.masters.fetch_states', return_value=[{'stateId': 2, 'state': 'Telangana'}])
    def test_doc_field_names_and_flags(self, *_mocks):
        from apps.aeps.services.onboarding import build_fingpay_merchant_payload

        merchant = MagicMock()
        merchant.merchant_login_id = 'MPAYTEST01'
        flat = {
            'firstName': 'Ramesh',
            'lastName': 'Kumar',
            'middleName': 'K',
            'merchantPhoneNumber': '9876543210',
            'emailId': 'ramesh@example.com',
            'merchantAddress1': 'Street One',
            'merchantAddress2': 'Near Market',
            'merchantState': 2,
            'merchantCityName': 'Hyderabad',
            'merchantDistrictName': 'Hyderabad',
            'merchantPinCode': '500001',
            'companyLegalName': 'Ramesh Traders',
            'companyType': 2,
            'userPan': 'ABCDE1234F',
            'aadhaarNumber': '999999990019',
            'gstinNumber': '29AAACT9999A1Z5',
            'companyOrShopPan': 'ABCDE1234F',
            'companyBankAccountNumber': '1234567890',
            'bankIfscCode': 'SBIN0000001',
            'companyBankName': 'State Bank of India',
            'bankBranchName': 'Abids',
            'bankAccountName': 'Ramesh Kumar',
            'shopAddress': 'Shop 12',
            'shopCity': 'Hyderabad',
            'shopDistrict': 'Hyderabad',
            'shopState': 2,
            'shopPincode': '500001',
        }
        payload = build_fingpay_merchant_payload(
            merchant=merchant, flat=flat, latitude=17.38, longitude=78.48, aadhaar_full='999999990019'
        )

        self.assertEqual(payload['merchantLoginPin'], '4821')  # plain PIN per doc
        self.assertEqual(payload['certificateOfIncorporationImage'], 'True')
        self.assertEqual(payload['kyc']['shopAndPanImage'], 'True')
        self.assertEqual(payload['videoKycWithLatLongData'], 'True')
        self.assertNotIn('vedioKycWithLatLongData', payload)
        self.assertIn('gstinNumber', payload['kyc'])
        self.assertEqual(payload['settlementV1']['bankBranchName'], 'Abids')
        self.assertIsInstance(payload['merchantKycAddressData']['shopLatitude'], float)
        self.assertIsInstance(payload['merchantKycAddressData']['shopLongitude'], float)
        self.assertIn(' ', payload['companyLegalName'])  # legal name keeps spaces
