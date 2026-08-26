from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch
import hashlib


_BIG_IMG = 'A' * 2500


class OnboardingPayloadMappingTests(SimpleTestCase):
    """Ensure MerchantModelV1 keys match Fingpay Simple API curl / docs."""

    @patch('apps.aeps.services.onboarding._use_plain_merchant_pin', return_value=False)
    @patch('apps.aeps.services.onboarding.merchant_pin_plain', return_value='4821')
    @patch(
        'apps.aeps.services.onboarding._provider_kyc_defaults',
        return_value={'gstinNumber': '', 'companyOrShopPan': '', 'userType': 'lakshmi'},
    )
    @patch(
        'apps.aeps.services.masters.resolve_company_type',
        side_effect=lambda v, _t=None: 4812 if str(v) in ('4', '4812') else (int(v) if str(v).isdigit() else None),
    )
    @patch('apps.aeps.services.masters.fetch_company_types', return_value=[
        {'id': 4, 'mccCode': 4812, 'companyType': 4812, 'mccDescription': 'Telecom'},
    ])
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
            'companyType': 4812,
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
            'merchantPanImage': _BIG_IMG,
            'maskedAadharImage': _BIG_IMG,
            'backgroundImageOfShop': _BIG_IMG,
        }
        payload = build_fingpay_merchant_payload(
            merchant=merchant, flat=flat, latitude=17.38, longitude=78.48, aadhaar_full='999999990019'
        )

        self.assertEqual(payload['merchantLoginPin'], hashlib.md5(b'4821').hexdigest())
        self.assertEqual(len(payload['merchantLoginPin']), 32)
        self.assertEqual(payload['userType'], 'lakshmi')
        self.assertEqual(payload['certificateOfIncorporationImage'], 'True')
        self.assertEqual(payload['kyc']['shopAndPanImage'], 'True')
        self.assertEqual(payload['videoKycWithLatLongData'], 'True')
        self.assertEqual(payload['vedioKycWithLatLongData'], 'True')
        self.assertIn('gstinNumber', payload['kyc'])
        self.assertEqual(payload['settlementV1']['bankBranchName'], 'Abids')
        self.assertIsInstance(payload['merchantKycAddressData']['shopLatitude'], float)
        self.assertIsInstance(payload['merchantKycAddressData']['shopLongitude'], float)
        self.assertIn(' ', payload['companyLegalName'])
        self.assertEqual(payload['companyType'], 4812)
        self.assertEqual(payload['kyc']['aadhaarNumber'], '999999990019')
        self.assertEqual(payload['kyc']['merchantPanImage'], _BIG_IMG)
        self.assertIsInstance(payload['merchantAddress']['merchantState'], int)
        # Fingpay 5009: strip & / parentheses from address lines
        self.assertNotIn('&', payload['merchantAddress']['merchantAddress1'])
        self.assertNotIn('(', payload['merchantAddress']['merchantAddress1'])

    @patch('apps.aeps.services.onboarding._use_plain_merchant_pin', return_value=True)
    @patch('apps.aeps.services.onboarding.merchant_pin_plain', return_value='default123')
    @patch(
        'apps.aeps.services.onboarding._provider_kyc_defaults',
        return_value={'gstinNumber': '', 'companyOrShopPan': '', 'userType': 'lakshmi'},
    )
    @patch('apps.aeps.services.masters.resolve_company_type', return_value=4812)
    @patch('apps.aeps.services.masters.fetch_company_types', return_value=[
        {'id': 4, 'mccCode': 4812, 'companyType': 4812},
    ])
    @patch('apps.aeps.services.masters.resolve_state_id', side_effect=lambda v, _s: int(v))
    @patch('apps.aeps.services.masters.fetch_states', return_value=[{'stateId': 2, 'state': 'Andhra Pradesh'}])
    def test_address_special_chars_stripped(self, *_mocks):
        from apps.aeps.services.onboarding import build_fingpay_merchant_payload

        merchant = MagicMock()
        merchant.merchant_login_id = 'MPH20182'
        flat = {
            'firstName': 'Jaggumanthri',
            'lastName': 'Kumar',
            'merchantPhoneNumber': '9550221153',
            'emailId': 'npsrkm1986@gmail.com',
            'merchantAddress1': 'Navodaya school, ravikamtham (village&mandal)',
            'merchantAddress2': 'near temple (gate-2)',
            'merchantState': 2,
            'merchantCityName': 'anakapalli',
            'merchantDistrictName': 'anakapalli',
            'merchantPinCode': '531025',
            'companyLegalName': 'Navodaya',
            'companyType': 4812,
            'userPan': 'KRAPK2170N',
            'gstinNumber': '37AAQCP8786M1Z4',
            'companyOrShopPan': 'KRAPK2170N',
            'companyBankAccountNumber': '35736936125',
            'bankIfscCode': 'SBIN0018204',
            'companyBankName': 'State Bank of India',
            'bankBranchName': 'Ravikamtham',
            'bankAccountName': 'Navodaya',
            'shopAddress': 'Navodaya school (village&mandal)',
            'shopCity': 'Anakapalli',
            'shopDistrict': 'Anakapalli',
            'shopState': 2,
            'shopPincode': '531025',
            'merchantPanImage': _BIG_IMG,
            'maskedAadharImage': _BIG_IMG,
            'backgroundImageOfShop': _BIG_IMG,
        }
        payload = build_fingpay_merchant_payload(
            merchant=merchant, flat=flat, latitude=17.38, longitude=78.48, aadhaar_full='287663698750'
        )
        a1 = payload['merchantAddress']['merchantAddress1']
        shop = payload['merchantKycAddressData']['shopAddress']
        self.assertEqual(a1, 'Navodaya school, ravikamtham village and mandal')
        self.assertNotRegex(a1, r'[&()]')
        self.assertNotRegex(shop, r'[&()]')
        self.assertIn('and', shop)

    @patch('apps.aeps.services.onboarding._use_plain_merchant_pin', return_value=True)
    @patch('apps.aeps.services.onboarding.merchant_pin_plain', return_value='default123')
    @patch(
        'apps.aeps.services.onboarding._provider_kyc_defaults',
        return_value={'gstinNumber': '', 'companyOrShopPan': '', 'userType': 'lakshmi'},
    )
    @patch('apps.aeps.services.masters.resolve_company_type', return_value=4812)
    @patch('apps.aeps.services.masters.fetch_company_types', return_value=[
        {'id': 4, 'mccCode': 4812, 'companyType': 4812},
    ])
    @patch('apps.aeps.services.masters.resolve_state_id', side_effect=lambda v, _s: int(v))
    @patch('apps.aeps.services.masters.fetch_states', return_value=[{'stateId': 2, 'state': 'Andhra Pradesh'}])
    def test_simple_api_plain_pin_and_legacy_company_id(self, *_mocks):
        from apps.aeps.services.onboarding import build_fingpay_merchant_payload

        merchant = MagicMock()
        merchant.merchant_login_id = 'MPH17497'
        flat = {
            'firstName': 'Jaggumanthri',
            'lastName': 'Kundan Uday Kumar',
            'middleName': 'test',
            'merchantPhoneNumber': '9550221153',
            'emailId': 'npsrkm1986@gmail.com',
            'merchantAddress1': '001 ravikamtham',
            'merchantAddress2': 'anakapalli anakapalli',
            'merchantState': 2,
            'merchantCityName': 'anakapalli',
            'merchantDistrictName': 'anakapalli',
            'merchantPinCode': '531025',
            'companyLegalName': 'uday 1234',
            'companyType': 4,  # legacy master row id → resolved to 4812
            'userPan': 'KRAPK2170N',
            'gstinNumber': '37AAQCP8786M1Z4',
            'companyOrShopPan': 'KRAPK2170N',
            'companyBankAccountNumber': '35736936125',
            'bankIfscCode': 'SBIN0018204',
            'companyBankName': 'State bank of india',
            'bankBranchName': 'ravikamtham',
            'bankAccountName': 'JAGGUMANTHRI KUNDAN UDAY KUMAR',
            'shopAddress': '001 RAVIKAMTHAM',
            'shopCity': 'ANAKAPALLI',
            'shopDistrict': 'ANAKAPALLI',
            'shopState': 2,
            'shopPincode': '531025',
            'merchantPanImage': _BIG_IMG,
            'maskedAadharImage': _BIG_IMG,
            'backgroundImageOfShop': _BIG_IMG,
        }
        payload = build_fingpay_merchant_payload(
            merchant=merchant,
            flat=flat,
            latitude=17.7934793,
            longitude=82.8010472,
            aadhaar_full='287663698750',
        )
        self.assertEqual(payload['merchantLoginPin'], 'default123')
        self.assertEqual(payload['companyType'], 4812)
        self.assertEqual(payload['kyc']['aadhaarNumber'], '287663698750')
        self.assertNotIn('vedioKycWithLatLongData', payload)
        self.assertEqual(payload['videoKycWithLatLongData'], 'True')

    @patch('apps.aeps.services.onboarding._use_plain_merchant_pin', return_value=True)
    @patch('apps.aeps.services.onboarding.merchant_pin_plain', return_value='1234')
    @patch(
        'apps.aeps.services.onboarding._provider_kyc_defaults',
        return_value={'gstinNumber': '29AAACT9999A1Z5', 'companyOrShopPan': 'ABCDE1234F', 'userType': 'lakshmi'},
    )
    @patch('apps.aeps.services.masters.resolve_company_type', return_value=4812)
    @patch('apps.aeps.services.masters.fetch_company_types', return_value=[])
    @patch('apps.aeps.services.masters.resolve_state_id', return_value=2)
    @patch('apps.aeps.services.masters.fetch_states', return_value=[{'stateId': 2, 'state': 'AP'}])
    def test_rejects_masked_aadhaar_and_tiny_images(self, *_mocks):
        from apps.aeps.services.onboarding import build_fingpay_merchant_payload
        from rest_framework.exceptions import ValidationError

        merchant = MagicMock()
        merchant.merchant_login_id = 'X'
        base = {
            'firstName': 'Aa',
            'lastName': 'Bb',
            'merchantPhoneNumber': '9999999999',
            'emailId': 'a@b.com',
            'merchantAddress1': 'addr',
            'merchantAddress2': 'address line',
            'merchantState': 2,
            'merchantCityName': 'c',
            'merchantDistrictName': 'd',
            'merchantPinCode': '531025',
            'companyType': 4812,
            'userPan': 'ABCDE1234F',
            'companyBankAccountNumber': '1',
            'bankIfscCode': 'SBIN0000001',
            'bankAccountName': 'n',
            'shopAddress': 's',
            'shopCity': 'c',
            'shopDistrict': 'd',
            'shopState': 2,
            'shopPincode': '531025',
            'merchantPanImage': _BIG_IMG,
            'maskedAadharImage': _BIG_IMG,
            'backgroundImageOfShop': _BIG_IMG,
        }
        with self.assertRaises(ValidationError):
            build_fingpay_merchant_payload(
                merchant=merchant, flat=base, latitude=1.0, longitude=2.0, aadhaar_full='xxxxxxxx8750'
            )
        with self.assertRaises(ValidationError):
            build_fingpay_merchant_payload(
                merchant=merchant,
                flat={**base, 'merchantPanImage': 'iVBORw0KGgo'},
                latitude=1.0,
                longitude=2.0,
                aadhaar_full='287663698750',
            )


class ResolveCompanyTypeTests(SimpleTestCase):
    def test_mcc_and_legacy_id(self):
        from apps.aeps.services.masters import resolve_company_type

        rows = [
            {'id': 4, 'mccCode': 4812, 'companyType': 4812},
            {'id': 24, 'mccCode': 5732, 'companyType': 5732},
        ]
        self.assertEqual(resolve_company_type(4812, rows), 4812)
        self.assertEqual(resolve_company_type(4, rows), 4812)
        self.assertEqual(resolve_company_type(24, rows), 5732)
        self.assertIsNone(resolve_company_type(99999, rows))


class ResetMerchantPinTests(SimpleTestCase):
    def test_invalid_new_pin_rejected(self):
        from rest_framework.exceptions import ValidationError
        from apps.aeps.services.onboarding import reset_merchant_pin_via_onboarding

        merchant = MagicMock()
        with self.assertRaises(ValidationError):
            reset_merchant_pin_via_onboarding(merchant=merchant, new_pin='12')
