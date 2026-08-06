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
