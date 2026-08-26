from django.test import SimpleTestCase

from apps.aeps.services.products import (
    ACK_CD,
    ACK_CD_OTP,
    ACK_CW,
    PATH_2FA,
    PATH_CD_OTP_GENERATE,
    PATH_CD_OTP_TXN,
    PATH_CD_OTP_VALIDATE,
    STATUS_PATHS,
    _base_merchant_fields,
    _card_from_payload,
    _merchant_mobile,
    _merchant_user_name,
    _super_merchant_id,
    _txn_merchant_pin,
    ack_path_for_product,
    status_path_for_product,
)


class AepsPathRoutingTests(SimpleTestCase):
    def test_2fa_path_is_tfauth(self):
        self.assertEqual(PATH_2FA, 'fpaepsservice/auth/tfauth/merchant/php/validate/aadhar')

    def test_status_paths_per_product(self):
        self.assertIn('cashWithdrawal/v2', status_path_for_product('CW'))
        self.assertIn('cashDeposit', status_path_for_product('CD'))
        self.assertIn('cashDepositWithOtp', status_path_for_product('CD', otp_mode=True))
        self.assertIn('cashDepositWithOtp', status_path_for_product('CD_OTP'))
        self.assertIn('aadhaarPay', status_path_for_product('AP'))
        self.assertEqual(status_path_for_product('BE'), STATUS_PATHS['BE'])

    def test_ack_paths_per_product(self):
        self.assertEqual(ack_path_for_product('CW'), ACK_CW)
        self.assertEqual(ack_path_for_product('CD'), ACK_CD)
        self.assertEqual(ack_path_for_product('CD', otp_mode=True), ACK_CD_OTP)
        self.assertEqual(ack_path_for_product('CD_OTP'), ACK_CD_OTP)
        self.assertEqual(ack_path_for_product('AP'), ACK_CW)

    def test_cd_otp_path_constants(self):
        self.assertTrue(PATH_CD_OTP_GENERATE.endswith('generate/otp'))
        self.assertTrue(PATH_CD_OTP_VALIDATE.endswith('validate/otp'))
        self.assertTrue(PATH_CD_OTP_TXN.endswith('/transaction'))


class AepsCdOtpStepMachineTests(SimpleTestCase):
    """Document expected CD OTP step transitions (no live Fingpay)."""

    ALLOWED = {
        'generate': {'otp_sent', 'generate_failed'},
        'otp_sent': {'otp_validated', 'otp_invalid'},
        'otp_validated': {'completed'},
    }

    def test_step_graph(self):
        self.assertIn('otp_sent', self.ALLOWED['generate'])
        self.assertIn('otp_validated', self.ALLOWED['otp_sent'])
        self.assertIn('completed', self.ALLOWED['otp_validated'])


class SimpleApiMerchantFieldsTests(SimpleTestCase):
    def test_super_merchant_id_is_int(self):
        client = type('C', (), {'super_merchant_id': '1501'})()
        self.assertEqual(_super_merchant_id(client), 1501)
        self.assertIsInstance(_super_merchant_id(client), int)

    def test_simple_api_pin_is_uppercase_md5(self):
        from unittest.mock import patch
        from apps.integrations.fingpay.crypto import md5_hex

        merchant = type('M', (), {})()
        client = type('C', (), {'api_mode': 'simple', 'onboarding_api_style': 'simple'})()
        with patch('apps.aeps.services.products.merchant_pin_plain', return_value='2590'):
            pin = _txn_merchant_pin(merchant, client)
        self.assertEqual(pin, md5_hex('2590').upper())

    def test_base_fields_include_submerchant_and_int_super_id(self):
        from unittest.mock import patch

        merchant = type('M', (), {
            'merchant_login_id': 'MPH17497',
            'onboarding_payload': {'merchantPhoneNumber': '9550221153'},
            'user': type('U', (), {'phone': '9550221153'})(),
        })()
        client = type('C', (), {
            'api_mode': 'simple',
            'onboarding_api_style': 'simple',
            'super_merchant_id': '1501',
            'super_merchant_login_id': 'Mpayhubd',
        })()
        with patch('apps.aeps.services.products.merchant_pin_plain', return_value='0033'):
            fields = _base_merchant_fields(merchant, client)
        self.assertEqual(fields['superMerchantId'], 1501)
        self.assertNotIn('subMerchantId', fields)
        self.assertEqual(fields['merchantUserName'], 'MPH17497')
        from apps.integrations.fingpay.crypto import md5_hex

        self.assertEqual(fields['merchantPin'], md5_hex('0033').upper())

    def test_merchant_user_name_is_login_id(self):
        merchant = type('M', (), {
            'merchant_login_id': 'MPH20182',
            'onboarding_payload': {'merchantPhoneNumber': '919550221153'},
            'user': type('U', (), {'phone': '9550221153'})(),
        })()
        self.assertEqual(_merchant_user_name(merchant), 'MPH20182')
        self.assertEqual(_merchant_mobile(merchant), '9550221153')

    def test_encrypted_api_pin_is_md5(self):
        from unittest.mock import patch
        from apps.integrations.fingpay.crypto import md5_hex

        merchant = type('M', (), {})()
        client = type('C', (), {'api_mode': 'encrypted', 'onboarding_api_style': 'java'})()
        with patch('apps.aeps.services.products.merchant_pin_plain', return_value='0033'):
            pin = _txn_merchant_pin(merchant, client)
        self.assertEqual(pin, md5_hex('0033'))

    def test_simple_txn_body_matches_ministatement_sample_order(self):
        from unittest.mock import patch

        merchant = type('M', (), {
            'merchant_login_id': 'MPH20182',
            'onboarding_payload': {'merchantPhoneNumber': '9550221153'},
            'user': type('U', (), {'phone': '9550221153'})(),
        })()
        client = type('C', (), {
            'api_mode': 'simple',
            'onboarding_api_style': 'simple',
            'super_merchant_id': '1501',
            'super_merchant_login_id': 'Mpayhubd',
        })()
        with patch('apps.aeps.services.products.merchant_pin_plain', return_value='2590'):
            from apps.aeps.services.products import _simple_txn_body
            body = _simple_txn_body(
                merchant=merchant,
                client=client,
                product='MS',
                payload={'mobileNumber': '9652488158', 'aadhaarNumber': '287663698750', 'iin': '607094'},
                capture_response={'fType': '0', 'errCode': '0'},
                latitude=17.79,
                longitude=82.80,
                amount=0,
                merchant_tran_id='MS20260813141308758334',
            )
        self.assertEqual(list(body.keys()), [
            'merchantTranId',
            'captureResponse',
            'cardnumberORUID',
            'languageCode',
            'latitude',
            'longitude',
            'mobileNumber',
            'paymentType',
            'requestRemarks',
            'timestamp',
            'transactionAmount',
            'transactionType',
            'merchantUserName',
            'merchantPin',
            'superMerchantId',
            'deviceTransactionId',
        ])
        self.assertEqual(body['transactionType'], 'MS')
        self.assertEqual(body['paymentType'], 'B')
        self.assertEqual(body['languageCode'], 'en')
        self.assertEqual(body['merchantUserName'], 'MPH20182')
        self.assertNotIn('subMerchantId', body)
        self.assertEqual(body['superMerchantId'], 1501)
        from apps.integrations.fingpay.crypto import md5_hex
        self.assertEqual(body['merchantPin'], md5_hex('2590').upper())
        self.assertEqual(body['cardnumberORUID']['adhaarNumber'], '287663698750')
        self.assertEqual(body['deviceTransactionId'], 'MS20260813141308758334')

    def test_card_coerces_iin_to_string(self):
        card = _card_from_payload({
            'aadhaarNumber': 287663698750,
            'nationalBankIdentificationNumber': 607094,
            'indicatorforUID': '0',
        })
        self.assertEqual(card['adhaarNumber'], '287663698750')
        self.assertEqual(card['nationalBankIdentificationNumber'], '607094')
        self.assertEqual(card['indicatorforUID'], 0)
