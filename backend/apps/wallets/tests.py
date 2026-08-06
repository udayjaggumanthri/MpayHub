from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.wallets.models import Wallet
from apps.wallets.portfolio import sum_network_wallet_balances
from apps.wallets.presentation import present_wallet_summary_for_viewer
from apps.wallets.views import build_wallet_summary

User = get_user_model()


class WalletHistoryDescriptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555555',
            email='wallet_history@test.com',
            password='testpass123',
            role='Admin',
            user_id='ADMIN99',
            first_name='Admin',
            last_name='User',
        )

    def test_profit_wallet_is_supported(self):
        profit = Wallet.get_wallet(self.user, 'profit')
        self.assertEqual(profit.wallet_type, 'profit')

    def test_credit_stores_business_description(self):
        profit = Wallet.get_wallet(self.user, 'profit')
        tx = profit.credit(Decimal('12.3400'), reference='TXN123', description='Admin profit on pay-in TXN123')
        self.assertEqual(tx.description, 'Admin profit on pay-in TXN123')
        self.assertEqual(tx.reference, 'TXN123')


class AdminNetworkWalletTotalsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9111111111',
            email='admin_portfolio@test.com',
            password='testpass123',
            role='Admin',
            user_id='A_PORT1',
            first_name='Admin',
            last_name='Portfolio',
        )
        self.r1 = User.objects.create_user(
            phone='9222222222',
            email='retailer1_portfolio@test.com',
            password='testpass123',
            role='Retailer',
            user_id='R_PORT1',
            first_name='Retailer',
            last_name='One',
        )
        self.r2 = User.objects.create_user(
            phone='9333333333',
            email='retailer2_portfolio@test.com',
            password='testpass123',
            role='Retailer',
            user_id='R_PORT2',
            first_name='Retailer',
            last_name='Two',
        )

        Wallet.get_wallet(self.admin, 'main').credit(Decimal('999.00'), reference='ADM-MAIN')
        Wallet.get_wallet(self.admin, 'bbps').credit(Decimal('888.00'), reference='ADM-BBPS')
        Wallet.get_wallet(self.admin, 'commission').credit(Decimal('50.00'), reference='ADM-COMM')
        Wallet.get_wallet(self.admin, 'profit').credit(Decimal('75.25'), reference='ADM-PROFIT')

        Wallet.get_wallet(self.r1, 'main').credit(Decimal('100.50'), reference='R1-MAIN')
        Wallet.get_wallet(self.r1, 'bbps').credit(Decimal('20.00'), reference='R1-BBPS')
        Wallet.get_wallet(self.r2, 'main').credit(Decimal('200.25'), reference='R2-MAIN')
        Wallet.get_wallet(self.r2, 'bbps').credit(Decimal('30.50'), reference='R2-BBPS')

    def test_sum_excludes_admin_wallets(self):
        totals = sum_network_wallet_balances()
        self.assertEqual(totals['main'], Decimal('300.75'))
        self.assertEqual(totals['bbps'], Decimal('50.50'))

    def test_presenter_replaces_admin_main_bbps_only(self):
        personal = build_wallet_summary(self.admin)
        presented = present_wallet_summary_for_viewer(self.admin, personal)
        self.assertEqual(presented['main']['balance'], '300.75')
        self.assertEqual(presented['main']['source'], 'network_total')
        self.assertEqual(presented['bbps']['balance'], '50.50')
        self.assertEqual(presented['bbps']['source'], 'network_total')
        self.assertEqual(Decimal(str(presented['commission']['balance'])), Decimal('50.00'))
        self.assertNotIn('source', presented['commission'])
        self.assertEqual(Decimal(str(presented['profit']['balance'])), Decimal('75.25'))

    def test_presenter_leaves_retailer_personal(self):
        personal = build_wallet_summary(self.r1)
        presented = present_wallet_summary_for_viewer(self.r1, personal)
        self.assertEqual(Decimal(str(presented['main']['balance'])), Decimal('100.50'))
        self.assertNotIn('source', presented['main'])
        self.assertEqual(Decimal(str(presented['bbps']['balance'])), Decimal('20.00'))

    def test_admin_get_wallets_api_returns_network_totals(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.get('/api/wallets/')
        self.assertEqual(res.status_code, 200)
        wallets = res.data['data']['wallets']
        self.assertEqual(wallets['main']['balance'], '300.75')
        self.assertEqual(wallets['main']['source'], 'network_total')
        self.assertEqual(wallets['bbps']['balance'], '50.50')
        self.assertEqual(Decimal(str(wallets['commission']['balance'])), Decimal('50.00'))
        self.assertEqual(Decimal(str(wallets['profit']['balance'])), Decimal('75.25'))

    def test_retailer_get_wallets_api_stays_personal(self):
        client = APIClient()
        client.force_authenticate(user=self.r1)
        res = client.get('/api/wallets/')
        self.assertEqual(res.status_code, 200)
        wallets = res.data['data']['wallets']
        self.assertEqual(Decimal(str(wallets['main']['balance'])), Decimal('100.50'))
        self.assertNotIn('source', wallets['main'])
        self.assertEqual(Decimal(str(wallets['bbps']['balance'])), Decimal('20.00'))
