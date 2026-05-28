from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.wallets.models import Wallet

User = get_user_model()


class AdminUserWalletsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9333333321',
            email='wallet-admin@test.com',
            password='secret123',
            role='Admin',
            user_id='WLTADM1',
        )
        self.retailer = User.objects.create_user(
            phone='9444444421',
            email='wallet-retailer@test.com',
            password='secret123',
            role='Retailer',
            user_id='WLTRT1',
        )
        self.other = User.objects.create_user(
            phone='9555555521',
            email='wallet-other@test.com',
            password='secret123',
            role='Retailer',
            user_id='WLTRT2',
        )
        Wallet.objects.create(user=self.retailer, wallet_type='main', balance=Decimal('1500.50'))
        Wallet.objects.create(user=self.retailer, wallet_type='bbps', balance=Decimal('200.00'))
        self.client = APIClient()

    def _url(self, user_pk):
        return f'/api/users/{user_pk}/wallets/'

    def test_admin_can_get_user_wallets(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.get(self._url(self.retailer.pk))
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body['success'])
        wallets = body['data']['wallets']
        self.assertEqual(wallets['main']['balance'], '1500.50')
        self.assertEqual(wallets['bbps']['balance'], '200.00')

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.retailer)
        r = self.client.get(self._url(self.other.pk))
        self.assertEqual(r.status_code, 403)

    def test_user_not_found_returns_404(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.get(self._url(999999))
        self.assertEqual(r.status_code, 404)
