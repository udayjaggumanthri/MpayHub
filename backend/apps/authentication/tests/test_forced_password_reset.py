from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.authentication.models import OTP
from apps.authentication.password_onboarding import issue_temporary_password

User = get_user_model()


class ForcedPasswordResetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone='9222222299',
            email='forced-reset@test.com',
            password='placeholder',
            role='Retailer',
            user_id='FCPW1',
        )
        self.temp_password = issue_temporary_password(self.user)

    def test_send_otp_requires_must_change_password(self):
        self.user.must_change_password = False
        self.user.save(update_fields=['must_change_password'])
        self.client.force_authenticate(user=self.user)
        r = self.client.post(
            '/api/auth/me/send-password-reset-otp/',
            {'channel': 'sms'},
            format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_complete_reset_clears_flag(self):
        self.client.force_authenticate(user=self.user)
        send_r = self.client.post(
            '/api/auth/me/send-password-reset-otp/',
            {'channel': 'sms'},
            format='json',
        )
        self.assertEqual(send_r.status_code, 200, send_r.content)
        otp = OTP.objects.filter(phone=self.user.phone, purpose='password-reset').latest('created_at')
        r = self.client.post(
            '/api/auth/me/complete-password-reset/',
            {
                'otp': otp.code,
                'new_password': 'NewSecure99',
                'confirm_password': 'NewSecure99',
            },
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body.get('success'))
        self.assertFalse(body['data']['user']['onboarding']['must_change_password'])
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.check_password('NewSecure99'))
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)
