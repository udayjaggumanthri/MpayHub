"""Tests for Admin scope=platform operational reports (dashboard drill-down parity)."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.bbps.models import BillPayment
from apps.fund_management.models import LoadMoney
from apps.transactions.models import PassbookEntry


def _user(phone, email, role, user_id):
    return User.objects.create_user(
        phone=phone,
        email=email,
        password='testpass123',
        role=role,
        user_id=user_id,
        first_name='T',
        last_name='User',
    )


class PlatformScopeReportTests(TestCase):
    def setUp(self):
        self.admin = _user('9000000001', 'admin-plat@test.com', 'Admin', 'ADMPLAT1')
        self.retailer = _user('9000000002', 'ret-plat@test.com', 'Retailer', 'RETPLAT1')
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin)
        self.retailer_client = APIClient()
        self.retailer_client.force_authenticate(user=self.retailer)

    def test_retailer_platform_scope_forbidden(self):
        r = self.retailer_client.get('/api/reports/payin/', {'scope': 'platform'})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_payin_includes_pending_load_money(self):
        LoadMoney.objects.create(
            user=self.retailer,
            amount=Decimal('500'),
            gateway='test',
            charge=Decimal('5'),
            net_credit=Decimal('495'),
            status='PENDING',
            transaction_id='LM-PLAT-PEND-1',
        )
        LoadMoney.objects.create(
            user=self.retailer,
            amount=Decimal('100'),
            gateway='test',
            charge=Decimal('1'),
            net_credit=Decimal('99'),
            status='SUCCESS',
            transaction_id='LM-PLAT-SUC-1',
        )
        r = self.admin_client.get(
            '/api/reports/payin/',
            {'scope': 'platform', 'status': 'PENDING'},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['data']['scope'], 'platform')
        self.assertEqual(r.data['data']['total'], 1)
        rows = r.data['data']['rows']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['service_id'], 'LM-PLAT-PEND-1')
        self.assertEqual(rows[0]['status'], 'PENDING')
        self.assertEqual(rows[0]['opening_balance'], '')
        self.assertEqual(rows[0]['closing_balance'], '')

    def test_platform_payin_success_includes_passbook_balances(self):
        LoadMoney.objects.create(
            user=self.retailer,
            amount=Decimal('200'),
            gateway='test',
            charge=Decimal('2'),
            net_credit=Decimal('198'),
            status='SUCCESS',
            transaction_id='LM-PLAT-BAL-1',
        )
        PassbookEntry.objects.create(
            user=self.retailer,
            wallet_type='main',
            service='LOAD MONEY',
            service_id='LM-PLAT-BAL-1',
            description='Load',
            credit_amount=Decimal('198'),
            debit_amount=Decimal('0'),
            opening_balance=Decimal('1000.0000'),
            closing_balance=Decimal('1198.0000'),
        )
        r = self.admin_client.get(
            '/api/reports/payin/',
            {'scope': 'platform', 'status': 'SUCCESS'},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        rows = [row for row in r.data['data']['rows'] if row['service_id'] == 'LM-PLAT-BAL-1']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['opening_balance'], '1000.0000')
        self.assertEqual(rows[0]['closing_balance'], '1198.0000')

    def test_platform_bbps_matches_bill_payment_not_transaction_only(self):
        BillPayment.objects.create(
            user=self.retailer,
            biller='Test Biller',
            bill_type='electricity',
            amount=Decimal('250'),
            charge=Decimal('2'),
            total_deducted=Decimal('252'),
            status='SUCCESS',
            service_id='BP-PLAT-1',
            request_id='req-1',
        )
        today = timezone.localdate().isoformat()
        r = self.admin_client.get(
            '/api/reports/bbps/',
            {
                'scope': 'platform',
                'status': 'SUCCESS',
                'date_from': today,
                'date_to': today,
            },
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(r.data['data']['total'], 1)
        ids = [row['transaction_id'] for row in r.data['data']['rows']]
        self.assertIn('BP-PLAT-1', ids)
        row = next(row for row in r.data['data']['rows'] if row['transaction_id'] == 'BP-PLAT-1')
        self.assertIn('opening_balance', row)
        self.assertIn('closing_balance', row)

    def test_self_scope_still_limits_to_own_user(self):
        LoadMoney.objects.create(
            user=self.admin,
            amount=Decimal('999'),
            gateway='test',
            charge=Decimal('1'),
            net_credit=Decimal('998'),
            status='SUCCESS',
            transaction_id='LM-ADMIN-HIDDEN',
        )
        LoadMoney.objects.create(
            user=self.retailer,
            amount=Decimal('50'),
            gateway='test',
            charge=Decimal('0.5'),
            net_credit=Decimal('49.5'),
            status='SUCCESS',
            transaction_id='LM-SELF-ONLY',
        )
        r = self.retailer_client.get('/api/reports/payin/', {'scope': 'self'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['data']['scope'], 'self')
        ids = [row['service_id'] for row in r.data['data']['rows']]
        self.assertEqual(ids, ['LM-SELF-ONLY'])
        self.assertNotIn('LM-ADMIN-HIDDEN', ids)
        self.assertEqual(r.data['data']['total'], 1)

    def test_payin_summary_uses_cache_on_repeat(self):
        from django.core.cache import cache
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        LoadMoney.objects.create(
            user=self.retailer,
            amount=Decimal('75'),
            gateway='test',
            charge=Decimal('1'),
            net_credit=Decimal('74'),
            status='SUCCESS',
            transaction_id='LM-SUM-CACHE-1',
        )
        cache.clear()
        with CaptureQueriesContext(connection) as first:
            r1 = self.admin_client.get('/api/reports/payin/', {'scope': 'platform'})
        with CaptureQueriesContext(connection) as second:
            r2 = self.admin_client.get('/api/reports/payin/', {'scope': 'platform'})
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data['data']['summary'], r2.data['data']['summary'])
        self.assertLess(len(second.captured_queries), len(first.captured_queries))
