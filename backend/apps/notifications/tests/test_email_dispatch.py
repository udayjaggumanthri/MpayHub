from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.admin_panel.models import SmtpConfig
from apps.notifications.models import EmailDeliveryLog, EmailNotificationTemplate
from apps.notifications.services.email_dispatch import EmailNotificationService

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailDispatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555599',
            email='dispatch@test.com',
            password='secret123',
            role='Retailer',
            user_id='EMLDSP1',
        )
        self.template = EmailNotificationTemplate.objects.get(
            event_key='auth.otp.password_reset',
            is_deleted=False,
        )
        self.template.is_enabled = True
        self.template.subject_template = 'Code {{otp}}'
        self.template.body_html_template = '<p>OTP: {{otp}}</p>'
        self.template.body_plain_template = 'OTP: {{otp}}'
        self.template.save()

        cfg = SmtpConfig.objects.create(
            name='test',
            host='smtp.test.com',
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

    @patch('apps.notifications.services.email_dispatch.send_email')
    def test_dispatch_sent(self, mock_send):
        result = EmailNotificationService.dispatch(
            'auth.otp.password_reset',
            self.user.email,
            {'otp': '123456', 'expiry_minutes': '5'},
            user_id=self.user.pk,
            idempotency_key='test:dispatch:sent',
        )
        self.assertEqual(result['status'], 'sent')
        mock_send.assert_called_once()
        log = EmailDeliveryLog.objects.get(idempotency_key='test:dispatch:sent')
        self.assertEqual(log.status, 'sent')

    def test_dispatch_skips_duplicate(self):
        EmailDeliveryLog.objects.create(
            event_key='auth.otp.password_reset',
            idempotency_key='test:dup',
            to_email_masked='d***@test.com',
            status='sent',
        )
        result = EmailNotificationService.dispatch(
            'auth.otp.password_reset',
            self.user.email,
            {'otp': '111111', 'expiry_minutes': '5'},
            idempotency_key='test:dup',
        )
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['skip_reason'], 'duplicate')

    def test_dispatch_skips_no_email(self):
        result = EmailNotificationService.dispatch(
            'auth.otp.password_reset',
            '',
            {'otp': '111111', 'expiry_minutes': '5'},
            idempotency_key='test:no-email',
        )
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['skip_reason'], 'no_email')

    def test_dispatch_skips_when_disabled(self):
        self.template.is_enabled = False
        self.template.save(update_fields=['is_enabled'])
        result = EmailNotificationService.dispatch(
            'auth.otp.password_reset',
            self.user.email,
            {'otp': '111111', 'expiry_minutes': '5'},
            idempotency_key='test:disabled',
        )
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['skip_reason'], 'event_disabled')

    def test_dispatch_skips_invalid_context(self):
        result = EmailNotificationService.dispatch(
            'auth.otp.password_reset',
            self.user.email,
            {'expiry_minutes': '5'},
            idempotency_key='test:bad-ctx',
        )
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['skip_reason'], 'invalid_context')
