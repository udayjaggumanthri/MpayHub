"""Tests for dashboard recent activity and today's summary widgets."""
from datetime import timedelta
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


def _lm(user, tid, st='SUCCESS', amount='100'):
    return LoadMoney.objects.create(
        user=user,
        amount=Decimal(amount),
        gateway='test',
        charge=Decimal('1'),
        net_credit=Decimal(amount) - Decimal('1'),
        status=st,
        transaction_id=tid,
    )


def _bill(user, sid, st='SUCCESS', amount='50'):
    return BillPayment.objects.create(
        user=user,
        biller='B1',
        bill_type='mobile',
        amount=Decimal(amount),
        charge=Decimal('1'),
        total_deducted=Decimal(amount) + Decimal('1'),
        status=st,
        service_id=sid,
    )


def _pb(user, sid, credit='0', debit='0'):
    credit_d = Decimal(credit)
    debit_d = Decimal(debit)
    return PassbookEntry.objects.create(
        user=user,
        wallet_type='main',
        service='test',
        service_id=sid,
        description='test',
        credit_amount=credit_d,
        debit_amount=debit_d,
        opening_balance=Decimal('1000'),
        closing_balance=Decimal('1000') + credit_d - debit_d,
    )


class DashboardHomeAPITests(TestCase):
    def setUp(self):
        self.retailer = _user('9000000201', 'retail-home@test.com', 'Retailer', 'RTLH1')
        self.other = _user('9000000202', 'other-home@test.com', 'Retailer', 'RTLH2')
        self.admin = _user('9000000203', 'admin-home@test.com', 'Admin', 'ADMH1')
        self.client = APIClient()
        _lm(self.retailer, 'LM-HOME-1', 'SUCCESS', '200')
        _bill(self.retailer, 'BP-HOME-1', 'PENDING', '75')
        _lm(self.other, 'LM-OTHER-1', 'SUCCESS', '999')
        _pb(self.retailer, 'PB-C1', credit='200')
        _pb(self.retailer, 'PB-D1', debit='75')
        _pb(self.other, 'PB-OTHER', credit='999')

    def test_retailer_recent_is_self_only(self):
        self.client.force_authenticate(user=self.retailer)
        r = self.client.get('/api/reports/dashboard/recent/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        items = r.data['data']['items']
        refs = {row['reference'] for row in items}
        self.assertIn('LM-HOME-1', refs)
        self.assertIn('BP-HOME-1', refs)
        self.assertNotIn('LM-OTHER-1', refs)
        payin = next(row for row in items if row['reference'] == 'LM-HOME-1')
        self.assertEqual(payin['type'], 'Load Money')
        self.assertEqual(payin['status'], 'SUCCESS')
        self.assertEqual(payin['signed'], 'credit')

    def test_retailer_summary_is_self_only(self):
        self.client.force_authenticate(user=self.retailer)
        r = self.client.get('/api/reports/dashboard/summary/', {'interval': 'daily'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.data['data']
        self.assertEqual(data['scope'], 'self')
        self.assertEqual(data['total_credits'], '200.00')
        self.assertEqual(data['total_debits'], '75.00')
        self.assertGreaterEqual(data['transaction_count'], 2)

    def test_admin_summary_is_platform_wide(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.get('/api/reports/dashboard/summary/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.data['data']
        self.assertEqual(data['scope'], 'platform')
        self.assertEqual(data['total_credits'], '1199.00')

    def test_unauthenticated_rejected(self):
        r = self.client.get('/api/reports/dashboard/recent/')
        self.assertIn(r.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_yesterday_does_not_inflate_today_credits(self):
        old = _pb(self.retailer, 'PB-OLD', credit='500')
        PassbookEntry.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        self.client.force_authenticate(user=self.retailer)
        r = self.client.get('/api/reports/dashboard/summary/')
        self.assertEqual(r.data['data']['total_credits'], '200.00')
