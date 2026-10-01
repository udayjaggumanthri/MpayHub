"""Tests for refund_mock_payouts (SUCCESS mock payout reverse)."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.bank_accounts.models import BankAccount
from apps.core.utils import encrypt_secret_payload
from apps.fund_management.management.commands.refund_mock_payouts import (
    ALLOWLIST_TXN_IDS,
    FAILURE_REASON,
    refund_one_mock_payout,
)
from apps.fund_management.models import Payout
from apps.transactions.models import CommissionLedger, PassbookEntry, Transaction
from apps.transactions.services.fee_settlement import settle_service_charge
from apps.wallets.models import Wallet

User = get_user_model()


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class RefundMockPayoutTests(TestCase):
    def setUp(self):
        self.treasury = User.objects.create_user(
            phone='9111111101',
            email='treasury_refund@test.com',
            password='pass12345',
            role='Admin',
            user_id='TREAS01',
            first_name='Treasury',
            last_name='User',
        )
        tw = Wallet.get_wallet(self.treasury, 'main')
        tw.balance = Decimal('1000.0000')
        tw.save(update_fields=['balance'])

        self.agent = User.objects.create_user(
            phone='9111111102',
            email='agent_refund@test.com',
            password='pass12345',
            role='Retailer',
            user_id='RAGREF1',
            first_name='Agent',
            last_name='Refund',
        )
        aw = Wallet.get_wallet(self.agent, 'main')
        aw.balance = Decimal('100.0000')
        aw.save(update_fields=['balance'])

        self.bank = BankAccount.objects.create(
            user=self.agent,
            account_number='38370894141',
            ifsc='SBIN0017978',
            bank_name='STATE BANK OF INDIA',
            account_holder_name='Test Beneficiary',
            is_verified=True,
        )

        # Use first allowlisted id so command subset checks aren't needed for unit helper
        self.tid = ALLOWLIST_TXN_IDS[0]
        self.payout = Payout.objects.create(
            user=self.agent,
            bank_account=self.bank,
            amount=Decimal('500.0000'),
            charge=Decimal('15.0000'),
            service_charge=Decimal('9.4400'),
            commission_amount=Decimal('5.5600'),
            platform_fee=Decimal('0'),
            total_deducted=Decimal('515.0000'),
            transfer_mode='IMPS',
            status='SUCCESS',
            transaction_id=self.tid,
            merchant_ref_id=self.tid,
            provider_code='vimopay',
            provider_txn_id='mock-txn-1',
            provider_status_code='000',
        )
        Transaction.objects.create(
            user=self.agent,
            transaction_type='payout',
            amount=Decimal('500.0000'),
            charge=Decimal('15.0000'),
            net_amount=Decimal('515.0000'),
            status='SUCCESS',
            service_id=self.tid,
            service_family='payout',
            reference='mock-txn-1',
        )
        # Simulate settle_service_charge slices (commission credited, fee tracker-only)
        settle_service_charge(
            payer=self.agent,
            module='payout',
            service_id=self.tid,
            charge=Decimal('15.0000'),
            principal=Decimal('500.0000'),
            slices=[
                {
                    'user': self.treasury,
                    'amount': Decimal('9.4400'),
                    'slice_key': 'platform_fee',
                    'entry_kind': 'service_fee',
                    'role_at_time': 'PLATFORM',
                    'source': 'payout',
                    'service_label': 'SERVICE FEE',
                    'description': f'PAYOUT service fee on {self.tid}',
                    'wallet_credited': False,
                },
                {
                    'user': self.treasury,
                    'amount': Decimal('5.5600'),
                    'slice_key': 'payout_admin',
                    'entry_kind': 'commission',
                    'role_at_time': 'PLATFORM',
                    'source': 'payout',
                    'service_label': 'COMMISSION',
                    'description': f'PAYOUT platform commission on {self.tid}',
                    'wallet_credited': True,
                },
            ],
            meta={'transfer_mode': 'IMPS'},
        )
        self.treasury.refresh_from_db()
        tw.refresh_from_db()
        self.treasury_main_after_settle = Wallet.get_wallet(self.treasury, 'main').balance

    def test_dry_run_does_not_mutate(self):
        before_agent = Wallet.get_wallet(self.agent, 'main').balance
        before_treas = Wallet.get_wallet(self.treasury, 'main').balance
        result = refund_one_mock_payout(payout=self.payout, dry_run=True)
        self.assertEqual(result['action'], 'dry_run')
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, 'SUCCESS')
        self.assertEqual(Wallet.get_wallet(self.agent, 'main').balance, before_agent)
        self.assertEqual(Wallet.get_wallet(self.treasury, 'main').balance, before_treas)

    def test_execute_refunds_and_is_idempotent(self):
        result = refund_one_mock_payout(payout=self.payout, dry_run=False)
        self.assertEqual(result['action'], 'refunded')

        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, 'FAILED')
        self.assertIn('mock/UAT', self.payout.failure_reason)
        self.assertIn('admin_refund', self.payout.response_meta)

        agent_bal = Wallet.get_wallet(self.agent, 'main').balance
        self.assertEqual(agent_bal, Decimal('615.0000'))  # 100 + 515

        treas_bal = Wallet.get_wallet(self.treasury, 'main').balance
        # commission 5.56 clawed back from treasury
        self.assertEqual(treas_bal, self.treasury_main_after_settle - Decimal('5.5600'))

        txn = Transaction.objects.get(service_id=self.tid, transaction_type='payout')
        self.assertEqual(txn.status, 'FAILED')

        self.assertTrue(
            PassbookEntry.objects.filter(service_id=self.tid, service='PAYOUT REFUND').exists()
        )
        self.assertTrue(
            CommissionLedger.objects.filter(
                reference_service_id=self.tid, slice_key__endswith='_reversal'
            ).exists()
        )

        # Idempotent second call
        again = refund_one_mock_payout(payout=self.payout, dry_run=False)
        self.assertEqual(again['action'], 'skipped_already_refunded')
        self.assertEqual(Wallet.get_wallet(self.agent, 'main').balance, Decimal('615.0000'))
