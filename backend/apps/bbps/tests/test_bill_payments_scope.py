"""Tests for scoped BBPS bill payments list (My Bills / Reports)."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.bbps.models import BillPayment
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


class BillPaymentsScopeTests(TestCase):
    def setUp(self):
        self.admin = _user('9100000001', 'bbps-adm@test.com', 'Admin', 'BBPSADM1')
        self.retailer = _user('9100000002', 'bbps-ret@test.com', 'Retailer', 'BBPSRET1')
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin)
        self.retailer_client = APIClient()
        self.retailer_client.force_authenticate(user=self.retailer)

    def _bp(self, user, sid, st='SUCCESS'):
        return BillPayment.objects.create(
            user=user,
            biller='Biller',
            bill_type='electricity',
            amount=Decimal('100'),
            charge=Decimal('1'),
            total_deducted=Decimal('101'),
            status=st,
            service_id=sid,
            request_id=f'req-{sid}',
        )

    def test_platform_scope_lists_all_users(self):
        self._bp(self.retailer, 'BP-SCOPE-1')
        r = self.admin_client.get('/api/bbps/payments/', {'scope': 'platform', 'page_size': 500})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [p['service_id'] for p in r.data['data']['payments']]
        self.assertIn('BP-SCOPE-1', ids)

    def test_self_scope_only_own(self):
        self._bp(self.retailer, 'BP-SELF-1')
        self._bp(self.admin, 'BP-ADM-1')
        r = self.retailer_client.get('/api/bbps/payments/', {'scope': 'self'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [p['service_id'] for p in r.data['data']['payments']]
        self.assertIn('BP-SELF-1', ids)
        self.assertNotIn('BP-ADM-1', ids)

    def test_retailer_platform_scope_forbidden(self):
        r = self.retailer_client.get('/api/bbps/payments/', {'scope': 'platform'})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_csv_platform(self):
        self._bp(self.retailer, 'BP-CSV-1')
        r = self.admin_client.get('/api/bbps/payments/export.csv', {'scope': 'platform'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('text/csv', r['Content-Type'])
        body = b''.join(r.streaming_content).decode('utf-8')
        self.assertIn('BP-CSV-1', body)
        self.assertIn('opening_balance', body)

    def test_list_includes_passbook_balances(self):
        self._bp(self.retailer, 'BP-BAL-1')
        PassbookEntry.objects.create(
            user=self.retailer,
            wallet_type='bbps',
            service='BBPS',
            service_id='BP-BAL-1',
            description='Bill pay',
            credit_amount=Decimal('0'),
            debit_amount=Decimal('101'),
            opening_balance=Decimal('500.0000'),
            closing_balance=Decimal('399.0000'),
        )
        r = self.retailer_client.get('/api/bbps/payments/', {'scope': 'self'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        row = next(p for p in r.data['data']['payments'] if p['service_id'] == 'BP-BAL-1')
        self.assertEqual(row['opening_balance'], '500.0000')
        self.assertEqual(row['closing_balance'], '399.0000')
