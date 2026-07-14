from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.authentication.serializers import UserSerializer
from apps.users.models import KYC, KycApprovalAudit
from apps.users.services import (
    admin_approve_kyc,
    admin_reject_kyc,
    setup_initial_mpin,
    sync_kyc_verification_status,
)

User = get_user_model()


class KycAdminApprovalWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9000000001',
            email='admin-kyc@test.com',
            password='secret123',
            role='Admin',
            user_id='ADMKYC1',
            first_name='Admin',
            last_name='User',
        )
        self.retailer = User.objects.create_user(
            phone='9000000002',
            email='retailer-kyc@test.com',
            password='secret123',
            role='Retailer',
            user_id='RTLKYC1',
            first_name='Retail',
            last_name='User',
        )
        self.kyc = KYC.objects.create(
            user=self.retailer,
            pan='ABCDE1234F',
            aadhaar='123456789012',
            pan_verified=True,
            aadhaar_verified=True,
            verification_status='pending',
        )

    @patch('apps.notifications.services.email_dispatch.EmailNotificationService.dispatch')
    def test_sync_sets_awaiting_approval_not_verified(self, mock_dispatch):
        sync_kyc_verification_status(self.kyc)
        self.kyc.refresh_from_db()
        self.assertEqual(self.kyc.verification_status, 'awaiting_approval')
        mock_dispatch.assert_called_once()
        self.assertEqual(mock_dispatch.call_args[0][0], 'kyc.submitted.for_approval')

        mock_dispatch.reset_mock()
        sync_kyc_verification_status(self.kyc)
        mock_dispatch.assert_not_called()

    def test_onboarding_gates_account_until_admin_verified(self):
        sync_kyc_verification_status(self.kyc)
        self.kyc.refresh_from_db()
        data = UserSerializer(self.retailer).data['onboarding']
        self.assertTrue(data['provider_kyc_complete'])
        self.assertTrue(data['awaiting_admin_approval'])
        self.assertFalse(data['kyc_complete'])
        self.assertFalse(data['account_ready'])

        admin_approve_kyc(self.admin, self.retailer)
        data = UserSerializer(self.retailer).data['onboarding']
        self.assertTrue(data['kyc_complete'])
        self.assertFalse(data['awaiting_admin_approval'])
        self.assertFalse(data['account_ready'])  # MPIN still required

        setup_initial_mpin(self.retailer, '123456', '123456')
        data = UserSerializer(self.retailer).data['onboarding']
        self.assertTrue(data['account_ready'])

    def test_mpin_blocked_before_admin_approval(self):
        sync_kyc_verification_status(self.kyc)
        with self.assertRaises(ValueError):
            setup_initial_mpin(self.retailer, '123456', '123456')

    @patch('apps.notifications.services.email_dispatch.EmailNotificationService.dispatch')
    def test_admin_approve_and_reject_audit(self, mock_dispatch):
        sync_kyc_verification_status(self.kyc)
        mock_dispatch.reset_mock()

        admin_approve_kyc(self.admin, self.retailer, notes='Looks good')
        self.kyc.refresh_from_db()
        self.assertEqual(self.kyc.verification_status, 'verified')
        self.assertEqual(self.kyc.decided_by_id, self.admin.pk)
        self.assertTrue(
            KycApprovalAudit.objects.filter(user=self.retailer, decision='approve').exists()
        )
        self.assertEqual(mock_dispatch.call_args[0][0], 'kyc.verification.complete')

        mock_dispatch.reset_mock()
        admin_reject_kyc(self.admin, self.retailer, notes='Name mismatch')
        self.kyc.refresh_from_db()
        self.assertEqual(self.kyc.verification_status, 'rejected')
        self.assertTrue(
            KycApprovalAudit.objects.filter(user=self.retailer, decision='reject').exists()
        )
        self.assertEqual(mock_dispatch.call_args[0][0], 'kyc.verification.rejected')

    def test_api_admin_approve_endpoint(self):
        sync_kyc_verification_status(self.kyc)
        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.post(
            f'/api/users/{self.retailer.pk}/kyc-approval/',
            {'decision': 'approve', 'notes': 'OK'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        self.kyc.refresh_from_db()
        self.assertEqual(self.kyc.verification_status, 'verified')

    def test_api_non_admin_forbidden(self):
        sync_kyc_verification_status(self.kyc)
        client = APIClient()
        client.force_authenticate(user=self.retailer)
        res = client.post(
            f'/api/users/{self.retailer.pk}/kyc-approval/',
            {'decision': 'approve'},
            format='json',
        )
        self.assertEqual(res.status_code, 403)
