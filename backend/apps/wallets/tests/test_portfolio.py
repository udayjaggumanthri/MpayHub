from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
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


@override_settings(PLATFORM_PAYIN_SETTLEMENT_USER_ID=None)
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
        self.admin2 = User.objects.create_user(
            phone='9111111112',
            email='admin2_portfolio@test.com',
            password='testpass123',
            role='Admin',
            user_id='A_PORT2',
            first_name='Admin',
            last_name='Two',
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
        Wallet.get_wallet(self.admin2, 'main').credit(Decimal('50.00'), reference='ADM2-MAIN')
        Wallet.get_wallet(self.r1, 'main').credit(Decimal('100.50'), reference='R1-MAIN')
        Wallet.get_wallet(self.r2, 'main').credit(Decimal('200.25'), reference='R2-MAIN')

    def test_sum_excludes_operator_wallets(self):
        totals = sum_network_wallet_balances()
        self.assertEqual(totals['main'], Decimal('300.75'))

    def test_presenter_keeps_treasury_main_adds_distributed(self):
        personal = build_wallet_summary(self.admin)
        presented = present_wallet_summary_for_viewer(self.admin, personal)
        self.assertEqual(Decimal(str(presented['main']['balance'])), Decimal('999.00'))
        self.assertIn('distributed', presented)
        self.assertEqual(presented['distributed']['balance'], '300.75')
        self.assertEqual(presented['distributed']['source'], 'network_total')

    def test_presenter_leaves_retailer_personal(self):
        personal = build_wallet_summary(self.r1)
        presented = present_wallet_summary_for_viewer(self.r1, personal)
        self.assertEqual(Decimal(str(presented['main']['balance'])), Decimal('100.50'))
        self.assertNotIn('distributed', presented)

    def test_admin_logins_share_treasury_main_via_api(self):
        """Every Admin login sees the same treasury Main (lowest-id Admin here)."""
        client = APIClient()
        client.force_authenticate(user=self.admin2)
        res = client.get('/api/wallets/')
        self.assertEqual(res.status_code, 200)
        wallets = res.data['data']['wallets']
        # admin2 login → treasury is self.admin (first Admin by id)
        self.assertEqual(Decimal(str(wallets['main']['balance'])), Decimal('999.00'))
        self.assertEqual(wallets['distributed']['balance'], '300.75')

    def test_retailer_get_wallets_api_stays_personal(self):
        client = APIClient()
        client.force_authenticate(user=self.r1)
        res = client.get('/api/wallets/')
        self.assertEqual(res.status_code, 200)
        wallets = res.data['data']['wallets']
        self.assertEqual(Decimal(str(wallets['main']['balance'])), Decimal('100.50'))
        self.assertNotIn('distributed', wallets)
