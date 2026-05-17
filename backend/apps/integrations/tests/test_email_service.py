from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.admin_panel.models import SmtpConfig
from apps.integrations.email_service import SMTP_BACKEND, _connection_from_config


class SmtpConnectionBackendTests(TestCase):
    def test_connection_uses_smtp_backend_not_console(self):
        cfg = SmtpConfig.objects.create(
            name='test-smtp',
            host='smtppro.zoho.in',
            port=587,
            use_tls=True,
            use_ssl=False,
            username='noreply@test.com',
            from_email='noreply@test.com',
            enabled=True,
            is_active=True,
        )
        cfg.set_password('secret')
        cfg.save()

        with patch('apps.integrations.email_service.get_connection') as mock_gc:
            mock_gc.return_value = MagicMock()
            _connection_from_config(cfg)
            mock_gc.assert_called_once()
            kwargs = mock_gc.call_args.kwargs
            self.assertEqual(kwargs['backend'], SMTP_BACKEND)
            self.assertEqual(kwargs['host'], 'smtppro.zoho.in')
            self.assertTrue(kwargs['use_tls'])
            self.assertFalse(kwargs['use_ssl'])
