from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.integrations.kyc.profile_comparator import compare_profile_with_kyc
from apps.integrations.kyc.profile_sync_orchestrator import (
    confirm_profile_sync,
    decline_profile_sync,
    handle_post_kyc_profile_sync,
)
from apps.users.models import KycProfileSyncAudit, UserProfile

User = get_user_model()


class KycProfileSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555801',
            email='sync@test.com',
            password='secret123',
            role='Retailer',
            user_id='SYNCRT1',
            first_name='Uday',
            last_name='J',
        )
        UserProfile.objects.create(
            user=self.user,
            first_name='Uday',
            last_name='J',
            date_of_birth=date(1990, 1, 15),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_compare_detects_name_mismatch(self):
        diff = compare_profile_with_kyc(
            self.user,
            verified_name='UDAY JAGGUMANTHRI',
            verified_dob=date(1990, 1, 15),
            source='pan',
        )
        self.assertTrue(diff.has_confirmation_mismatch)
        self.assertTrue(diff.name_differs)
        self.assertFalse(diff.dob_differs)

    @override_settings(KYC_PROFILE_SYNC_REQUIRE_CONFIRM_ON_MISMATCH=True)
    def test_mismatch_creates_pending_audit(self):
        result = handle_post_kyc_profile_sync(
            self.user,
            source='pan',
            trigger='test',
            verified_name='UDAY JAGGUMANTHRI',
            verified_dob=date(1990, 1, 15),
        )
        self.assertEqual(result.status, 'pending_confirmation')
        self.assertFalse(result.profile_updated)
        audit = KycProfileSyncAudit.objects.get(user=self.user)
        self.assertEqual(audit.status, 'pending')
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Uday')

    @override_settings(KYC_PROFILE_SYNC_REQUIRE_CONFIRM_ON_MISMATCH=True)
    def test_confirm_applies_profile_and_audits(self):
        pending = handle_post_kyc_profile_sync(
            self.user,
            source='pan',
            trigger='test',
            verified_name='UDAY JAGGUMANTHRI',
            verified_dob=date(1993, 6, 30),
        )
        result = confirm_profile_sync(self.user, sync_token=pending.sync_token)
        self.assertTrue(result.profile_updated)
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, 'UDAY JAGGUMANTH')
        self.assertEqual(self.user.last_name, 'RI')
        self.assertEqual(self.user.profile.date_of_birth, date(1993, 6, 30))
        audit = KycProfileSyncAudit.objects.get(sync_token=pending.sync_token)
        self.assertEqual(audit.status, 'applied')
        self.assertEqual(audit.after_first_name, 'UDAY JAGGUMANTH')

    @override_settings(KYC_PROFILE_SYNC_REQUIRE_CONFIRM_ON_MISMATCH=True)
    def test_decline_leaves_profile_unchanged(self):
        pending = handle_post_kyc_profile_sync(
            self.user,
            source='aadhaar',
            trigger='test',
            verified_name='UDAY JAGGUMANTHRI',
            verified_dob=date(1993, 6, 30),
        )
        result = decline_profile_sync(self.user, sync_token=pending.sync_token)
        self.assertFalse(result.profile_updated)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Uday')
        audit = KycProfileSyncAudit.objects.get(sync_token=pending.sync_token)
        self.assertEqual(audit.status, 'declined')

    @override_settings(KYC_PROFILE_SYNC_AUTO_FILL_EMPTY=True, KYC_PROFILE_SYNC_REQUIRE_CONFIRM_ON_MISMATCH=True)
    def test_empty_profile_dob_auto_fills_without_prompt(self):
        self.user.profile.date_of_birth = None
        self.user.profile.save(update_fields=['date_of_birth', 'updated_at'])
        result = handle_post_kyc_profile_sync(
            self.user,
            source='pan',
            trigger='test',
            verified_name='Uday J',
            verified_dob=date(1993, 6, 30),
        )
        self.assertEqual(result.status, 'auto_applied')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.date_of_birth, date(1993, 6, 30))

    def test_pending_api_lists_offers(self):
        handle_post_kyc_profile_sync(
            self.user,
            source='pan',
            trigger='test',
            verified_name='OTHER NAME',
            verified_dob=date(1993, 6, 30),
        )
        resp = self.client.get('/api/auth/me/profile-sync/pending/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['data']['pending']), 1)
