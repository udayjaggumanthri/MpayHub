from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.notifications.models import EmailDeliveryLog
from apps.users.models import KYC
from apps.users.services import sync_kyc_verification_status

User = get_user_model()


class KycEmailNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555588',
            email='kyc@test.com',
            password='secret123',
            role='Retailer',
            user_id='KYCEML1',
        )
        self.kyc = KYC.objects.create(
            user=self.user,
            pan='ABCDE1234F',
            aadhaar='123456789012',
            pan_verified=True,
            aadhaar_verified=True,
            verification_status='pending',
        )

    @patch('apps.notifications.services.email_dispatch.EmailNotificationService.dispatch')
    def test_sync_kyc_dispatches_once_on_verified(self, mock_dispatch):
        sync_kyc_verification_status(self.kyc)
        self.kyc.refresh_from_db()
        self.assertEqual(self.kyc.verification_status, 'verified')
        mock_dispatch.assert_called_once()
        args, kwargs = mock_dispatch.call_args
        self.assertEqual(args[0], 'kyc.verification.complete')
        self.assertEqual(args[1], 'kyc@test.com')
        self.assertEqual(kwargs['idempotency_key'], f'kyc:verified:{self.user.pk}')

        mock_dispatch.reset_mock()
        sync_kyc_verification_status(self.kyc)
        mock_dispatch.assert_not_called()
