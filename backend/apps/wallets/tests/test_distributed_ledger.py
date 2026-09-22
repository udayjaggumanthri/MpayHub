from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import UserHierarchy
from apps.wallets.models import Wallet
from apps.wallets.portfolio import list_distributed_ledger, list_user_network_ledger

User = get_user_model()


class DistributedLedgerApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9111000001',
            email='dist_admin@test.local',
            password='TestPass1!',
            role='Admin',
            user_id='A_DIST1',
            first_name='Admin',
            last_name='One',
        )
        self.md = User.objects.create_user(
            phone='9111000002',
            email='dist_md@test.local',
            password='TestPass1!',
            role='Master Distributor',
            user_id='MD_DIST1',
            first_name='MD',
            last_name='One',
        )
        self.d1 = User.objects.create_user(
            phone='9111000003',
            email='dist_d@test.local',
            password='TestPass1!',
            role='Distributor',
            user_id='D_DIST1',
            first_name='Dist',
            last_name='One',
        )
        self.r1 = User.objects.create_user(
            phone='9111000004',
            email='dist_r@test.local',
            password='TestPass1!',
            role='Retailer',
            user_id='R_DIST1',
            first_name='Ret',
            last_name='One',
        )
        UserHierarchy.objects.create(parent_user=self.md, child_user=self.d1)
        UserHierarchy.objects.create(parent_user=self.d1, child_user=self.r1)
        Wallet.get_wallet(self.md, 'main').credit(Decimal('100.00'), reference='md')
        Wallet.get_wallet(self.d1, 'main').credit(Decimal('50.00'), reference='d')
        Wallet.get_wallet(self.r1, 'main').credit(Decimal('25.00'), reference='r')
        Wallet.get_wallet(self.admin, 'main').credit(Decimal('999.00'), reference='a')

    def test_list_excludes_admin_by_default(self):
        data = list_distributed_ledger(page=1, page_size=50)
        ids = {u['id'] for u in data['users']}
        self.assertNotIn(self.admin.pk, ids)
        self.assertIn(self.r1.pk, ids)
        self.assertEqual(Decimal(data['summary']['filtered_balance']), Decimal('175.0000'))

    def test_role_filter_distributor(self):
        data = list_distributed_ledger(role='Distributor', page=1, page_size=50)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['users'][0]['id'], self.d1.pk)
        self.assertTrue(data['users'][0]['has_network'])

    def test_admin_shared_wallet_no_network(self):
        data = list_distributed_ledger(viewer=self.admin, role='Admin', page=1, page_size=50)
        self.assertTrue(data['summary']['shared_wallet'])
        self.assertTrue(all(u['shared_wallet'] for u in data['users']))
        self.assertTrue(all(not u['has_network'] for u in data['users']))
        self.assertNotIn('Super Admin', data['roles'])

    def test_network_hides_operator_role_filter(self):
        data = list_user_network_ledger(manager_id=self.md.pk, role='Admin', page=1, page_size=50)
        self.assertEqual(data['total'], 0)
        self.assertIn('empty_reason', data['summary'])
        self.assertNotIn('Admin', data['roles'])
        self.assertNotIn('Super Admin', data['roles'])

    def test_network_under_md(self):
        data = list_user_network_ledger(manager_id=self.md.pk, page=1, page_size=50)
        ids = {u['id'] for u in data['users']}
        self.assertEqual(ids, {self.d1.pk, self.r1.pk})
        self.assertEqual(Decimal(data['summary']['network_balance']), Decimal('75.0000'))

    def test_api_requires_admin(self):
        client = APIClient()
        client.force_authenticate(user=self.r1)
        res = client.get('/api/wallets/distributed/ledger/')
        self.assertIn(res.status_code, (403, 401))

    def test_api_ok_for_admin(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.get('/api/wallets/distributed/ledger/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        res2 = client.get(f'/api/wallets/distributed/network/{self.d1.pk}/')
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.data['data']['total'], 1)
