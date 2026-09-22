"""Channel users must not see peer commission slices in revenue breakdown."""
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.transactions.models import CommissionLedger


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


class RevenueBreakdownPrivacyTests(TestCase):
    def setUp(self):
        self.admin = _user('9100000001', 'adm-rev@test.com', 'Admin', 'ADMREV1')
        self.distributor = _user('9100000002', 'dist-rev@test.com', 'Distributor', 'DISTREV1')
        self.peer = _user('9100000003', 'md-rev@test.com', 'Master Distributor', 'MDREV1')
        self.ref = 'REV-PRIVACY-TXN-1'

        common = dict(
            reference_service_id=self.ref,
            source='bbps',
            module='bbps',
            entry_kind='commission',
            customer_charge=Decimal('5.0000'),
            wallet_type='main',
        )
        CommissionLedger.objects.create(
            user=self.distributor,
            role_at_time='Distributor',
            amount=Decimal('1.5000'),
            slice_key='Distributor',
            **common,
        )
        CommissionLedger.objects.create(
            user=self.peer,
            role_at_time='Master Distributor',
            amount=Decimal('2.0000'),
            slice_key='Master Distributor',
            **common,
        )
        CommissionLedger.objects.create(
            user=self.admin,
            role_at_time='Admin',
            amount=Decimal('1.5000'),
            slice_key='admin_absorbed',
            entry_kind='service_fee',
            reference_service_id=self.ref,
            source='bbps',
            module='bbps',
            customer_charge=Decimal('5.0000'),
            wallet_type='main',
        )

        self.dist_client = APIClient()
        self.dist_client.force_authenticate(user=self.distributor)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin)

    def test_distributor_sees_only_own_credit(self):
        r = self.dist_client.get(f'/api/reports/revenue/breakdown/{self.ref}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.data['data']
        self.assertIs(data.get('full_split'), False)
        self.assertEqual(Decimal(data['my_share']), Decimal('1.5000'))
        self.assertEqual(data.get('slices') or [], [])
        self.assertEqual(data.get('slice_count'), 0)
        self.assertNotIn('customer_charge', data)
        # Peer amounts / codes must not appear in the payload.
        blob = str(r.data)
        self.assertNotIn('2.0000', blob)
        self.assertNotIn(self.peer.user_id, blob)
        self.assertNotIn('Master Distributor', blob)

    def test_admin_sees_full_split(self):
        r = self.admin_client.get(f'/api/reports/revenue/breakdown/{self.ref}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.data['data']
        self.assertIs(data.get('full_split'), True)
        self.assertEqual(len(data.get('slices') or []), 3)
        self.assertIn('customer_charge', data)
        amounts = {Decimal(s['amount']) for s in data['slices']}
        self.assertEqual(amounts, {Decimal('1.5000'), Decimal('2.0000')})

    def test_list_hides_customer_charge_for_channel(self):
        r = self.dist_client.get('/api/reports/revenue/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ledger = r.data['data']['ledger']
        self.assertTrue(ledger)
        for row in ledger:
            self.assertEqual(row.get('customer_charge'), '')
