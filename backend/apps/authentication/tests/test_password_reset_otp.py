from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.mail import get_connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.admin_panel.models import SmtpConfig
from apps.authentication.models import OTP

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetOtpChannelTests(TestCase):
    def setUp(self):
        self._smtp_conn_patch = patch(
            'apps.integrations.email_service._connection_from_config',
            side_effect=lambda _cfg: get_connection(),
        )
        self._smtp_conn_patch.start()
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone='9555555502',
            email='reset-otp@test.com',
            password='secret123',
            role='Retailer',
            user_id='RSTOTP1',
        )
        cfg = SmtpConfig.objects.create(
            name='test',
            host='smtppro.zoho.in',
            port=587,
            use_tls=True,
            use_ssl=False,
            username='noreply@test.com',
            from_email='noreply@test.com',
            enabled=True,
            is_active=True,
        )
        cfg.set_password('smtp-test-password')
        cfg.save(update_fields=['password_encrypted'])

    def tearDown(self):
        self._smtp_conn_patch.stop()

    def test_send_otp_sms_default_unchanged(self):
        r = self.client.post(
            '/api/auth/send-otp/',
            {'phone': self.user.phone, 'purpose': 'password-reset'},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json().get('success'))
        self.assertEqual(len(mail.outbox), 0)
        otp = OTP.objects.filter(phone=self.user.phone, purpose='password-reset').latest('created_at')
        self.assertEqual(otp.delivery_channel, 'sms')

    def test_send_otp_email_delivers_to_registered_email(self):
        mail.outbox.clear()
        r = self.client.post(
            '/api/auth/send-otp/',
            {'phone': self.user.phone, 'purpose': 'password-reset', 'channel': 'email'},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body.get('success'))
        self.assertIn('registered email', body.get('message', '').lower())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn('password reset', mail.outbox[0].subject.lower())
        otp = OTP.objects.filter(phone=self.user.phone, purpose='password-reset').latest('created_at')
        self.assertEqual(otp.delivery_channel, 'email')
        self.assertIn(otp.code, mail.outbox[0].body)

    def test_send_otp_email_without_smtp_config_returns_400(self):
        SmtpConfig.objects.all().update(enabled=False, is_active=False)
        r = self.client.post(
            '/api/auth/send-otp/',
            {'phone': self.user.phone, 'purpose': 'password-reset', 'channel': 'email'},
            format='json',
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(r.json().get('success'))

    def test_aadhaar_rejects_email_channel(self):
        r = self.client.post(
            '/api/auth/send-otp/',
            {'phone': self.user.phone, 'purpose': 'aadhaar-verification', 'channel': 'email'},
            format='json',
        )
        self.assertEqual(r.status_code, 400, r.content)

    def test_user_without_email_cannot_use_email_channel(self):
        self.user.email = ''
        self.user.save(update_fields=['email'])
        r = self.client.post(
            '/api/auth/send-otp/',
            {'phone': self.user.phone, 'purpose': 'password-reset', 'channel': 'email'},
            format='json',
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(r.json().get('success'))
