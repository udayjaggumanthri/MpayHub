"""Query-budget checks for GET /api/auth/me/ (no duplicate KYC SELECTs)."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.users.models import KYC, UserProfile

User = get_user_model()


class AuthMeQueryBudgetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555599',
            email='me-budget@test.com',
            password='secret123',
            role='Retailer',
            user_id='MEBUD1',
            first_name='Me',
            last_name='Budget',
        )
        KYC.objects.create(user=self.user, verification_status='pending')
        UserProfile.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_me_avoids_duplicate_kyc_queries(self):
        """
        View already select_related('kyc','profile'); serializer must not re-query KYC twice.
        """
        self.client.get('/api/auth/me/')
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get('/api/auth/me/')
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()['data']['user']
        self.assertIn('onboarding', data)
        self.assertIn('kyc_verification', data)
        self.assertEqual(data['onboarding']['kyc_status'], 'pending')
        kyc_table_hits = [
            q['sql']
            for q in ctx.captured_queries
            if ' FROM "kyc" ' in q['sql'] or ' FROM "kyc"\n' in q['sql'] or 'JOIN "kyc"' in q['sql']
        ]
        # One JOIN via select_related is OK; no standalone KYC SELECT.
        standalone = [s for s in kyc_table_hits if 'JOIN "kyc"' not in s and 'LEFT OUTER JOIN "kyc"' not in s]
        self.assertEqual(len(standalone), 0, standalone)
        self.assertLessEqual(len(ctx.captured_queries), 6)

    def test_serializer_uses_select_related_kyc(self):
        from apps.authentication.serializers import UserSerializer

        user = User.objects.select_related('kyc', 'profile').get(pk=self.user.pk)
        with CaptureQueriesContext(connection) as ctx:
            payload = UserSerializer(user).data
        standalone_kyc = [
            q['sql']
            for q in ctx.captured_queries
            if ' FROM "kyc" ' in q['sql'] or q['sql'].rstrip().endswith('FROM "kyc"')
        ]
        self.assertEqual(len(standalone_kyc), 0, standalone_kyc)
        self.assertEqual(payload['onboarding']['kyc_status'], 'pending')
