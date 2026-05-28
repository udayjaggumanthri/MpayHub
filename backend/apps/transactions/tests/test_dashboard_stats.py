"""Tests for admin dashboard transaction status counts."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.bbps.models import BillPayment
from apps.fund_management.models import LoadMoney
from apps.transactions.dashboard_stats import (
    aggregate_module_counts,
    count_status_for_queryset,
    get_dashboard_transaction_status,
    resolve_period,
)


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


def _lm(user, tid, st, days_ago=0):
    lm = LoadMoney.objects.create(
        user=user,
        amount=Decimal('100'),
        gateway='test',
        charge=Decimal('1'),
        net_credit=Decimal('99'),
        status=st,
        transaction_id=tid,
    )
    if days_ago:
        LoadMoney.objects.filter(pk=lm.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
    return lm


class DashboardStatsServiceTests(TestCase):
    def setUp(self):
        self.user = _user('9111222333', 'dash@test.com', 'Retailer', 'DASH01')

    def test_count_status_for_queryset(self):
        _lm(self.user, 'LM-P1', 'PENDING')
        _lm(self.user, 'LM-S1', 'SUCCESS')
        _lm(self.user, 'LM-S2', 'SUCCESS')
        _lm(self.user, 'LM-F1', 'FAILED')
        qs = LoadMoney.objects.filter(is_deleted=False)
        counts = count_status_for_queryset(qs)
        self.assertEqual(counts['PENDING'], 1)
        self.assertEqual(counts['SUCCESS'], 2)
        self.assertEqual(counts['FAILED'], 1)
        self.assertEqual(counts['total'], 4)

    def test_aggregate_module_payin_only(self):
        _lm(self.user, 'LM-A1', 'PENDING')
        _lm(self.user, 'LM-A2', 'SUCCESS')
        today = timezone.localdate()
        totals, by_module = aggregate_module_counts('payin', today, today)
        self.assertIsNone(by_module)
        self.assertEqual(totals['PENDING'], 1)
        self.assertEqual(totals['SUCCESS'], 1)
        self.assertEqual(totals['total'], 2)

    def test_aggregate_all_modules_sums_by_module(self):
        _lm(self.user, 'LM-B1', 'SUCCESS')
        BillPayment.objects.create(
            user=self.user,
            biller='B1',
            bill_type='mobile',
            amount=Decimal('50'),
            charge=Decimal('1'),
            total_deducted=Decimal('51'),
            status='PENDING',
            service_id='BP-P1',
        )
        today = timezone.localdate()
        totals, by_module = aggregate_module_counts('all', today, today)
        self.assertIsNotNone(by_module)
        self.assertEqual(totals['PENDING'], by_module['payin']['PENDING'] + by_module['bbps']['PENDING'])
        self.assertEqual(totals['SUCCESS'], by_module['payin']['SUCCESS'] + by_module['bbps']['SUCCESS'])
        self.assertEqual(
            totals['total'],
            by_module['payin']['total'] + by_module['payout']['total'] + by_module['bbps']['total'],
        )

    def test_resolve_period_monthly_default(self):
        today = timezone.localdate()
        df, dt, interval = resolve_period('monthly', None, None)
        self.assertEqual(interval, 'monthly')
        self.assertEqual(df, today.replace(day=1))
        self.assertEqual(dt, today)

    def test_old_records_excluded_from_daily_today(self):
        _lm(self.user, 'LM-OLD', 'SUCCESS', days_ago=40)
        _lm(self.user, 'LM-TODAY', 'PENDING', days_ago=0)
        today = timezone.localdate()
        totals, _ = aggregate_module_counts('payin', today, today)
        self.assertEqual(totals['PENDING'], 1)
        self.assertEqual(totals['SUCCESS'], 0)


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
)
class DashboardStatsAPITests(TestCase):
    def setUp(self):
        self.admin = _user('9000000101', 'admin-dash@test.com', 'Admin', 'ADMDASH1')
        self.retailer = _user('9000000102', 'retail-dash@test.com', 'Retailer', 'RTLDASH1')
        self.client = APIClient()
        _lm(self.retailer, 'LM-API-1', 'SUCCESS')

    def test_admin_get_ok(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.get('/api/reports/dashboard/transaction-status-counts/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['success'])
        data = r.data['data']
        self.assertIn('counts', data)
        self.assertIn('PENDING', data['counts'])
        self.assertIn('by_module', data)
        self.assertEqual(data['module'], 'all')

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.retailer)
        r = self.client.get('/api/reports/dashboard/transaction-status-counts/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_module_filter_payin(self):
        self.client.force_authenticate(user=self.admin)
        BillPayment.objects.create(
            user=self.retailer,
            biller='X',
            bill_type='dth',
            amount=Decimal('10'),
            charge=Decimal('0'),
            total_deducted=Decimal('10'),
            status='FAILED',
            service_id='BP-ONLY-BBPS',
        )
        r = self.client.get(
            '/api/reports/dashboard/transaction-status-counts/',
            {'module': 'payin', 'interval': 'daily'},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        counts = r.data['data']['counts']
        self.assertEqual(counts['SUCCESS'], 1)
        self.assertEqual(counts['FAILED'], 0)
        self.assertNotIn('by_module', r.data['data'])

    def test_get_dashboard_transaction_status_cached(self):
        today = timezone.localdate().isoformat()
        p1 = get_dashboard_transaction_status(
            module='all',
            interval='daily',
            date_from_raw=today,
            date_to_raw=today,
            use_cache=True,
        )
        p2 = get_dashboard_transaction_status(
            module='all',
            interval='daily',
            date_from_raw=today,
            date_to_raw=today,
            use_cache=True,
        )
        self.assertEqual(p1['counts'], p2['counts'])
