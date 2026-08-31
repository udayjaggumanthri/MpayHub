from pathlib import Path

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


class ProviderFailureMessageTests(SimpleTestCase):
    """The outer envelope says "Transaction failed."; the cause lives in `data`."""

    def test_uidai_missing_biometric_is_explained(self):
        from apps.aeps.services.products import explain_provider_failure

        resp = {'status': False, 'message': 'Transaction failed.', 'statusCode': 10016}
        data = {
            'responseCode': '3552-E',
            'responseMessage': 'Missing biometric data as specified in Uses',
        }
        msg = explain_provider_failure(resp, data)
        self.assertIn('3552-E', msg)
        self.assertIn('Missing biometric data', msg)
        self.assertNotEqual(msg, 'Transaction failed.')

    def test_inner_message_preferred_over_generic_envelope(self):
        from apps.aeps.services.products import explain_provider_failure

        resp = {'status': False, 'message': 'Transaction failed.', 'statusCode': 10016}
        data = {'responseCode': '91', 'responseMessage': 'Issuer or switch inoperative'}
        self.assertEqual(
            explain_provider_failure(resp, data), 'Issuer or switch inoperative (91)'
        )

    def test_falls_back_to_envelope_when_data_empty(self):
        from apps.aeps.services.products import explain_provider_failure

        resp = {'status': False, 'message': 'Transaction failed.', 'statusCode': 10016}
        self.assertEqual(explain_provider_failure(resp, {}), 'Transaction failed.')

    def test_10027_daily_be_limit_is_not_aeps_disabled(self):
        from apps.aeps.services.products import explain_provider_failure

        resp = {
            'status': False,
            'statusCode': 10027,
            'message': 'You have exceeded daily limit of Balance Inquiry transactions',
        }
        msg = explain_provider_failure(resp, {})
        self.assertIn('daily limit', msg.lower())
        self.assertIn('Balance enquiry has a per-day cap', msg)
        self.assertNotIn('disabled AEPS', msg)
        self.assertNotIn('Tapits must enable', msg)

    def test_10027_temporarily_disabled_still_asks_tapits(self):
        from apps.aeps.services.products import explain_provider_failure

        resp = {
            'status': False,
            'statusCode': 10027,
            'message': 'AEPS services is temporarily disabled for this merchant',
        }
        msg = explain_provider_failure(resp, {})
        self.assertIn('disabled AEPS', msg)
        self.assertIn('Tapits must enable', msg)


class _FakeTxn:
    def __init__(self):
        self.merchant = None
        self.response_code = ''
        self.response_message = ''
        self.fp_transaction_id = ''
        self.bank_rrn = ''
        self.bank_name = ''
        self.balance_amount = None
        self.mini_statement = []
        self.provider_meta = {}
        self.status = 'initiated'

    def save(self, **kwargs):
        pass


class ApplyProviderResultTests(SimpleTestCase):
    def test_success_be_stores_balance_and_skips_sentinel(self):
        from decimal import Decimal

        from apps.aeps.services.products import apply_provider_result, _parse_balance_amount

        self.assertIsNone(_parse_balance_amount({'balanceAmount': -1}))
        self.assertEqual(_parse_balance_amount({'balanceAmount': 0}), Decimal('0'))

        txn = _FakeTxn()
        resp = {'status': True, 'statusCode': 10000, 'message': 'Success'}
        data = {
            'responseCode': '00',
            'responseMessage': 'Request Completed',
            'bankRRN': '624313221111',
            'balanceAmount': 65.02,
        }
        apply_provider_result(txn, resp, data)
        self.assertEqual(txn.status, 'success')
        self.assertEqual(txn.balance_amount, Decimal('65.02'))

    def test_success_ms_empty_lines_still_keeps_balance(self):
        from decimal import Decimal

        from apps.aeps.services.products import apply_provider_result

        txn = _FakeTxn()
        resp = {'status': True, 'statusCode': 10000}
        data = {
            'responseCode': '00',
            'responseMessage': 'Request Completed',
            'bankRRN': '624313229891',
            'balanceAmount': 65.02,
            'miniStatementBalance': '65.02',
            'miniOffusFlag': False,
            'miniStatementStructureModel': [],
            'miniOffusStatementStructureModel': [],
        }
        apply_provider_result(txn, resp, data)
        self.assertEqual(txn.status, 'success')
        self.assertEqual(txn.balance_amount, Decimal('65.02'))
        self.assertEqual(txn.mini_statement, [])

    def test_ms_falls_back_to_offus_lines(self):
        from apps.aeps.services.products import apply_provider_result

        txn = _FakeTxn()
        line = {'date': '31-08-2026', 'narration': 'ATM WDL', 'amount': '100.00', 'txnType': 'Dr'}
        resp = {'status': True, 'statusCode': 10000}
        data = {
            'responseCode': '00',
            'bankRRN': '624313229900',
            'balanceAmount': '10.00',
            'miniStatementStructureModel': [],
            'miniOffusStatementStructureModel': [line],
        }
        apply_provider_result(txn, resp, data)
        self.assertEqual(txn.mini_statement, [line])

    def test_mini_statement_balance_used_when_balance_amount_missing(self):
        from decimal import Decimal

        from apps.aeps.services.products import _parse_balance_amount

        self.assertEqual(
            _parse_balance_amount({'miniStatementBalance': '65.02'}),
            Decimal('65.02'),
        )


class CaptureGuardTests(SimpleTestCase):
    def test_capture_without_pid_block_is_rejected(self):
        from rest_framework.exceptions import ValidationError

        from apps.aeps.services.products import assert_capture_has_biometric

        for bad in ({}, {'Piddata': ''}, {'errCode': '0'}, None, 'x'):
            with self.assertRaises(ValidationError):
                assert_capture_has_biometric(bad)

    def test_capture_with_pid_block_passes(self):
        from apps.aeps.services.products import assert_capture_has_biometric, normalize_capture_response

        assert_capture_has_biometric({'Piddata': 'BASE64=='})
        assert_capture_has_biometric({'PidData': 'BASE64=='})
        out = normalize_capture_response({'Piddata': 'BASE64==', 'extra': 'drop', 'iType': ''})
        self.assertEqual(out['Piddata'], 'BASE64==')
        self.assertEqual(out['iType'], '0')
        self.assertEqual(out['pType'], '0')
        self.assertEqual(out['fType'], '2')
        self.assertNotIn('extra', out)
        from apps.aeps.services.products import CAPTURE_RESPONSE_KEYS

        self.assertEqual(list(out.keys()), list(CAPTURE_RESPONSE_KEYS))

    def test_raw_xml_as_piddata_is_rejected(self):
        from rest_framework.exceptions import ValidationError

        from apps.aeps.services.products import normalize_capture_response

        with self.assertRaises(ValidationError):
            normalize_capture_response({'Piddata': '<PidData><Data>x</Data></PidData>'})


class TwoFARequestBodyTests(SimpleTestCase):
    def test_sample_key_order_and_no_timestamp(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from apps.aeps.services.products import twofa_request_body

        merchant = SimpleNamespace(merchant_login_id='9550221153')
        client = SimpleNamespace(super_merchant_id='1501', api_mode='simple', onboarding_api_style='simple')
        with patch('apps.aeps.services.products._txn_merchant_pin', return_value='ABCD'):
            body = twofa_request_body(
                merchant=merchant,
                client=client,
                capture_response={'PidDatatype': 'X', 'Piddata': 'abc'},
                latitude=17.79,
                longitude=82.80,
                payload={
                    'aadhaarNumber': '287663698750',
                    'mobileNumber': '9550221153',
                    'nationalBankIdentificationNumber': '607094',
                },
                merchant_tran_id='2FA20260831120000000000',
                service_type='AEPS',
            )

        self.assertEqual(
            list(body.keys()),
            [
                'captureResponse',
                'cardnumberORUID',
                'latitude',
                'longitude',
                'requestRemarks',
                'transactionType',
                'merchantUserName',
                'merchantPin',
                'superMerchantId',
                'merchantTranId',
                'mobileNumber',
                'serviceType',
            ],
        )
        self.assertNotIn('timestamp', body)
        self.assertEqual(body['transactionType'], 'AUO')
        self.assertEqual(body['serviceType'], 'AEPS')
        self.assertEqual(body['merchantUserName'], '9550221153')

    def test_success_requires_inner_00(self):
        from apps.aeps.services.products import twofa_is_success

        self.assertTrue(twofa_is_success({'responseCode': '00'}))
        self.assertFalse(twofa_is_success({'responseCode': '3552-F'}))
        self.assertFalse(twofa_is_success({}))
        # Envelope 10000 without inner 00 is not success
        self.assertFalse(twofa_is_success({'responseCode': '10000'}))


class MantraRdContractTests(SimpleTestCase):
    JS = (
        Path(__file__).resolve().parents[4]
        / 'frontend'
        / 'src'
        / 'modules'
        / 'aeps'
        / 'services'
        / 'mantraRd.js'
    )

    def test_aeps_pidoptions_omit_empty_wadh_and_otp(self):
        src = self.JS.read_text(encoding='utf-8')
        self.assertTrue(self.JS.exists(), str(self.JS))
        self.assertIn("aeps: '2'", src)
        self.assertIn('wadh="${EKYC_WADH}"', src)
        self.assertNotIn('otp=""', src)
        self.assertNotIn("wadh=\"\"", src)

    def test_xml_mapper_extracts_documented_keys(self):
        import json
        import subprocess

        xml = (
            '<?xml version="1.0"?>'
            '<PidData>'
            '<Resp errCode="0" errInfo="Capture Success" fCount="1" fType="2" '
            'iCount="0" iType="0" pCount="0" pType="0" nmPoints="26" qScore="80"/>'
            '<DeviceInfo dpId="MANTRA.L1" rdsId="MANTRA.AND.001" rdsVer="1.0.1" '
            'dc="DC1" mi="L1AVDM" mc="MCERT"/>'
            '<Skey ci="20150822">SESSIONKEY</Skey>'
            '<Hmac>HMACVALUE</Hmac>'
            '<Data type="X">PIDBASE64</Data>'
            '</PidData>'
        )
        script = (
            "import { xmlToCaptureResponse, buildPidOptions } from %s;\n"
            "const mapped = xmlToCaptureResponse(%s);\n"
            "const aeps = buildPidOptions({ purpose: 'aeps' });\n"
            "const ekyc = buildPidOptions({ purpose: 'ekyc' });\n"
            "console.log(JSON.stringify({ mapped, aeps, ekyc }));\n"
            % (json.dumps(self.JS.resolve().as_uri()), json.dumps(xml))
        )
        proc = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        cap = payload['mapped']['captureResponse']
        self.assertEqual(cap['Piddata'], 'PIDBASE64')
        self.assertEqual(cap['PidDatatype'], 'X')
        self.assertEqual(cap['ci'], '20150822')
        self.assertEqual(cap['dpID'], 'MANTRA.L1')
        self.assertEqual(cap['fType'], '2')
        self.assertEqual(cap['iType'], '0')
        self.assertEqual(cap['sessionKey'], 'SESSIONKEY')
        self.assertEqual(
            list(cap.keys()),
            [
                'PidDatatype',
                'Piddata',
                'ci',
                'dc',
                'dpID',
                'errCode',
                'errInfo',
                'fCount',
                'fType',
                'hmac',
                'iCount',
                'iType',
                'mc',
                'mi',
                'nmPoints',
                'pCount',
                'pType',
                'qScore',
                'rdsID',
                'rdsVer',
                'sessionKey',
            ],
        )
        self.assertNotIn('wadh=', payload['aeps'])
        self.assertNotIn('otp=', payload['aeps'])
        self.assertIn('wadh=', payload['ekyc'])

    def test_xml_mapper_fails_when_data_missing(self):
        import json
        import subprocess

        xml = '<PidData><Resp errCode="0" errInfo="ok"/></PidData>'
        script = (
            "import { xmlToCaptureResponse } from %s;\n"
            "console.log(JSON.stringify(xmlToCaptureResponse(%s)));\n"
            % (json.dumps(self.JS.resolve().as_uri()), json.dumps(xml))
        )
        proc = subprocess.run(
            ['node', '--input-type=module', '-e', script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertIn('error', payload)
        self.assertNotIn('captureResponse', payload)
