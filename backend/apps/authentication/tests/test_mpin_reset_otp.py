from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.mail import get_connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.admin_panel.models import SmtpConfig
from apps.authentication.models import OTP
from apps.notifications.models import EmailNotificationTemplate

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MpinResetOtpTests(TestCase):
    def setUp(self):
        self._smtp_conn_patch = patch(
            'apps.integrations.email_service._connection_from_config',
            side_effect=lambda _cfg: get_connection(),
        )
        self._smtp_conn_patch.start()
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone='9555555533',
            email='mpin-reset@test.com',
            password='secret123',
            role='Retailer',
            user_id='MPNRST1',
        )
        self.user.set_mpin('654321')
        self.user.save(update_fields=['mpin_hash'])
        cfg = SmtpConfig.objects.create(
            name='test-mpin',
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

    def test_send_mpin_reset_otp_email(self):
        mail.outbox.clear()
        r = self.client.post(
            '/api/auth/send-otp/',
            {'phone': self.user.phone, 'purpose': 'mpin-reset', 'channel': 'email'},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json().get('success'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('mpin', mail.outbox[0].subject.lower())
        otp = OTP.objects.filter(phone=self.user.phone, purpose='mpin-reset').latest('created_at')
        self.assertEqual(otp.delivery_channel, 'email')

    def test_send_mpin_reset_requires_existing_mpin(self):
        bare = User.objects.create_user(
            phone='9666666633',
            email='no-mpin@test.com',
            password='secret123',
            role='Retailer',
            user_id='MPNRST2',
        )
        r = self.client.post(
            '/api/auth/send-otp/',
            {'phone': bare.phone, 'purpose': 'mpin-reset', 'channel': 'sms'},
            format='json',
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('not set', r.json().get('message', '').lower())

    def test_reset_mpin_after_otp(self):
        self.client.post(
            '/api/auth/send-otp/',
            {'phone': self.user.phone, 'purpose': 'mpin-reset', 'channel': 'sms'},
            format='json',
        )
        otp = OTP.objects.filter(phone=self.user.phone, purpose='mpin-reset').latest('created_at')
        r = self.client.post(
            '/api/auth/reset-mpin/',
            {
                'phone': self.user.phone,
                'otp': otp.code,
                'new_mpin': '112233',
                'confirm_mpin': '112233',
            },
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_mpin('112233'))
        self.assertFalse(self.user.check_mpin('654321'))

    def test_mpin_reset_email_uses_admin_template(self):
        tpl = EmailNotificationTemplate.objects.get(
            event_key='auth.otp.mpin_reset',
            is_deleted=False,
        )
        tpl.is_enabled = True
        tpl.subject_template = 'MPIN code: {{otp}}'
        tpl.body_plain_template = 'MPIN OTP {{otp}}'
        tpl.save()

        mail.outbox.clear()
        r = self.client.post(
            '/api/auth/send-otp/',
            {'phone': self.user.phone, 'purpose': 'mpin-reset', 'channel': 'email'},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('MPIN code:', mail.outbox[0].subject)
