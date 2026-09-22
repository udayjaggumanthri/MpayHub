"""
Tests for wallet consolidation helpers and fee settlement.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.transactions.models import CommissionLedger, PassbookEntry
from apps.transactions.services.fee_settlement import settle_service_charge
from apps.wallets.consolidation import dry_run, merge_user, reconcile
from apps.wallets.models import Wallet, WalletMergeAudit

User = get_user_model()


class WalletHoldTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9000000001',
            email='hold@test.local',
            password='TestPass1!',
        )
        self.main = Wallet.get_wallet(self.user, 'main')
        self.main.credit(Decimal('1000.00'), reference='seed')

    def test_hold_reduces_available_not_balance(self):
        self.main.hold(Decimal('100.00'), reference='H1')
        self.main.refresh_from_db()
        self.assertEqual(self.main.balance, Decimal('1000.0000'))
        self.assertEqual(self.main.held_balance, Decimal('100.0000'))
        self.assertEqual(self.main.available_balance, Decimal('900.0000'))

    def test_settle_hold_debits_balance(self):
        self.main.hold(Decimal('50.00'), reference='H2')
        self.main.settle_hold(Decimal('50.00'), reference='H2')
        self.main.refresh_from_db()
        self.assertEqual(self.main.balance, Decimal('950.0000'))
        self.assertEqual(self.main.held_balance, Decimal('0.0000'))

    def test_release_hold(self):
        self.main.hold(Decimal('40.00'), reference='H3')
        self.main.release(Decimal('40.00'), reference='H3')
        self.main.refresh_from_db()
        self.assertEqual(self.main.balance, Decimal('1000.0000'))
        self.assertEqual(self.main.held_balance, Decimal('0.0000'))
        self.assertEqual(self.main.available_balance, Decimal('1000.0000'))


class WalletMergeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9000000002',
            email='merge@test.local',
            password='TestPass1!',
        )
        Wallet.get_wallet(self.user, 'main').credit(Decimal('100.00'), reference='m')
        Wallet.get_wallet(self.user, 'bbps').credit(Decimal('25.50'), reference='b')
        Wallet.get_wallet(self.user, 'commission').credit(Decimal('10.00'), reference='c')
        Wallet.get_wallet(self.user, 'profit').credit(Decimal('5.25'), reference='p')

    def test_merge_conserves_paisa(self):
        audit = merge_user(self.user)
        self.assertEqual(audit.status, 'merged')
        self.assertEqual(audit.merged_total, Decimal('40.7500'))
        main = Wallet.get_wallet(self.user, 'main')
        self.assertEqual(main.balance, Decimal('140.7500'))
        for wt in ('bbps', 'commission', 'profit'):
            w = Wallet.objects.get(user=self.user, wallet_type=wt)
            self.assertEqual(w.balance, Decimal('0.0000'))
            self.assertTrue(w.is_archived)
        self.assertTrue(
            PassbookEntry.objects.filter(user=self.user, service='WALLET MERGE').exists()
        )

    def test_dry_run_no_money_moved(self):
        summary = dry_run(write_csv_path=None)
        self.assertGreaterEqual(summary['users'], 1)
        bbps = Wallet.objects.get(user=self.user, wallet_type='bbps')
        self.assertEqual(bbps.balance, Decimal('25.5000'))
        self.assertTrue(WalletMergeAudit.objects.filter(status='dry_run').exists())


class FeeSettlementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9000000003',
            email='admin@test.local',
            password='TestPass1!',
        )
        self.admin.role = 'Admin'
        self.admin.save(update_fields=['role'])
        self.payer = User.objects.create_user(
            phone='9000000004',
            email='payer@test.local',
            password='TestPass1!',
        )
        Wallet.get_wallet(self.admin, 'main')
        Wallet.get_wallet(self.payer, 'main').credit(Decimal('500.00'), reference='seed')

    def test_settle_service_charge_credits_admin_main(self):
        rows = settle_service_charge(
            payer=self.payer,
            module='bbps',
            service_id='SVCTEST001',
            charge=Decimal('5.00'),
            principal=Decimal('100.00'),
        )
        self.assertTrue(rows)
        admin_main = Wallet.get_wallet(self.admin, 'main')
        self.assertEqual(admin_main.balance, Decimal('5.0000'))
        ledger = CommissionLedger.objects.filter(reference_service_id='SVCTEST001')
        self.assertTrue(ledger.exists())
        self.assertEqual(ledger.first().entry_kind, 'service_fee')
        self.assertEqual(ledger.first().module, 'bbps')

    def test_settle_idempotent(self):
        settle_service_charge(
            payer=self.payer,
            module='payout',
            service_id='SVCIDEMP1',
            charge=Decimal('7.00'),
            principal=Decimal('200.00'),
        )
        settle_service_charge(
            payer=self.payer,
            module='payout',
            service_id='SVCIDEMP1',
            charge=Decimal('7.00'),
            principal=Decimal('200.00'),
        )
        admin_main = Wallet.get_wallet(self.admin, 'main')
        self.assertEqual(admin_main.balance, Decimal('7.0000'))
        self.assertEqual(
            CommissionLedger.objects.filter(reference_service_id='SVCIDEMP1').count(),
            1,
        )

    def test_settle_full_charge_to_single_admin_when_multiple_exist(self):
        other = User.objects.create_user(
            phone='9000000005',
            email='admin2@test.local',
            password='TestPass1!',
        )
        other.role = 'Admin'
        other.save(update_fields=['role'])
        Wallet.get_wallet(other, 'main')

        settle_service_charge(
            payer=self.payer,
            module='bbps',
            service_id='SVCFULL5',
            charge=Decimal('5.00'),
            principal=Decimal('1000.00'),
        )
        self.assertEqual(Wallet.get_wallet(self.admin, 'main').balance, Decimal('5.0000'))
        self.assertEqual(Wallet.get_wallet(other, 'main').balance, Decimal('0.0000'))
        ledgers = CommissionLedger.objects.filter(reference_service_id='SVCFULL5')
        self.assertEqual(ledgers.count(), 1)
        self.assertEqual(ledgers.first().user_id, self.admin.pk)
        self.assertEqual(ledgers.first().amount, Decimal('5.0000'))
