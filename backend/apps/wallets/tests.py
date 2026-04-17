from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.wallets.models import Wallet

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
