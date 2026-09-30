"""
Tests for admin/platform profit backfill — no double-credit, idempotent apply.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.bbps.models import BillPayment
from apps.fund_management.commission_meta import commission_ledger_create
from apps.transactions.models import CommissionLedger
from apps.wallets.models import Wallet

User = get_user_model()


@override_settings(PLATFORM_PAYIN_SETTLEMENT_USER_ID=None)
class BackfillPlatformAdminProfitTests(TestCase):
    def setUp(self):
        self.sa = User.objects.create_user(
            phone='9100000001',
            email='sa_bf@test.local',
            password='TestPass1!',
            role='Super Admin',
            user_id='SA_BF1',
            first_name='Super',
            last_name='Admin',
        )
        self.admin = User.objects.create_user(
            phone='9100000002',
            email='admin_bf@test.local',
            password='TestPass1!',
            role='Admin',
            user_id='AD_BF1',
            first_name='Admin',
            last_name='One',
        )
        self.agent = User.objects.create_user(
            phone='9100000003',
            email='agent_bf@test.local',
            password='TestPass1!',
            role='Retailer',
            user_id='RT_BF1',
            first_name='Retailer',
            last_name='One',
        )
        # Seed wallets: SA holds booked payin leftover; Admin holds BBPS booked.
        Wallet.get_wallet(self.sa, 'main').credit(Decimal('100.00'), reference='sa-seed')
        Wallet.get_wallet(self.admin, 'main').credit(Decimal('50.00'), reference='ad-seed')
        Wallet.get_wallet(self.agent, 'main').credit(Decimal('1000.00'), reference='ag-seed')

        commission_ledger_create(
            user=self.sa,
            role_at_time='PLATFORM_ADMIN',
            amount=Decimal('100.00'),
            source='payin',
            entry_kind='service_fee',
            module='payin',
            slice_key='admin_absorbed',
            customer_charge=Decimal('100.00'),
            reference_service_id='PMLM-SEED-1',
            wallet_type='main',
            meta={
                'slice': 'admin_absorbed',
                'wallet_credited': True,
                'source_user_id': self.agent.pk,
            },
        )
        commission_ledger_create(
            user=self.admin,
            role_at_time='PLATFORM',
            amount=Decimal('10.00'),
            source='bbps',
            entry_kind='service_fee',
            module='bbps',
            slice_key='platform_fee',
            customer_charge=Decimal('10.00'),
            reference_service_id='PMBBPS-BOOKED-1',
            wallet_type='main',
            meta={
                'slice': 'platform_fee',
                'wallet_credited': True,
                'source_user_id': self.agent.pk,
            },
        )
        # Unbooked BBPS SUCCESS with charge (gap).
        BillPayment.objects.create(
            user=self.agent,
            biller='Test Biller',
            bill_type='ELECTRICITY',
            amount=Decimal('200.00'),
            charge=Decimal('5.00'),
            total_deducted=Decimal('205.00'),
            status='SUCCESS',
            service_id='PMBBPS-GAP-1',
        )
        # Payout tracker row — must stay service_fee.
        commission_ledger_create(
            user=self.admin,
            role_at_time='PLATFORM',
            amount=Decimal('7.00'),
            source='payout',
            entry_kind='service_fee',
            module='payout',
            slice_key='platform_fee',
            customer_charge=Decimal('7.00'),
            reference_service_id='PMPO-KEEP-1',
            wallet_type='main',
            meta={
                'slice': 'platform_fee',
                'wallet_credited': False,
                'source_user_id': self.agent.pk,
            },
        )

    def test_dry_run_no_writes(self):
        sa_before = Wallet.get_wallet(self.sa, 'main').balance
        ad_before = Wallet.get_wallet(self.admin, 'main').balance
        call_command(
            'backfill_platform_admin_profit',
            '--dry-run',
            f'--from-user={self.sa.pk}',
            f'--to-user={self.admin.pk}',
        )
        self.assertEqual(Wallet.get_wallet(self.sa, 'main').balance, sa_before)
        self.assertEqual(Wallet.get_wallet(self.admin, 'main').balance, ad_before)
        self.assertEqual(
            CommissionLedger.objects.filter(
                reference_service_id='PMLM-SEED-1', entry_kind='service_fee'
            ).count(),
            1,
        )
        self.assertFalse(
            CommissionLedger.objects.filter(reference_service_id='PMBBPS-GAP-1').exists()
        )

    def test_apply_reclass_books_bbps_unifies_once(self):
        call_command(
            'backfill_platform_admin_profit',
            f'--from-user={self.sa.pk}',
            f'--to-user={self.admin.pk}',
        )
        # A: reclassed
        payin = CommissionLedger.objects.get(reference_service_id='PMLM-SEED-1')
        self.assertEqual(payin.entry_kind, 'commission')
        self.assertEqual(payin.user_id, self.admin.pk)  # unified onto treasury
        bbps_booked = CommissionLedger.objects.get(reference_service_id='PMBBPS-BOOKED-1')
        self.assertEqual(bbps_booked.entry_kind, 'commission')
        # D: payout untouched
        payout = CommissionLedger.objects.get(reference_service_id='PMPO-KEEP-1')
        self.assertEqual(payout.entry_kind, 'service_fee')

        # B: gap booked once
        gap = CommissionLedger.objects.get(reference_service_id='PMBBPS-GAP-1')
        self.assertEqual(gap.entry_kind, 'commission')
        self.assertEqual(gap.amount, Decimal('5.0000'))
        self.assertEqual(gap.user_id, self.admin.pk)

        # Wallet: SA emptied of moved amount; Admin gained SA 100 + BBPS gap 5
        sa_main = Wallet.get_wallet(self.sa, 'main')
        ad_main = Wallet.get_wallet(self.admin, 'main')
        self.assertEqual(sa_main.balance, Decimal('0.0000'))
        self.assertEqual(ad_main.balance, Decimal('155.0000'))  # 50 + 100 + 5

        # Second apply: no double credit
        call_command(
            'backfill_platform_admin_profit',
            f'--from-user={self.sa.pk}',
            f'--to-user={self.admin.pk}',
        )
        self.assertEqual(Wallet.get_wallet(self.admin, 'main').balance, Decimal('155.0000'))
        self.assertEqual(
            CommissionLedger.objects.filter(reference_service_id='PMBBPS-GAP-1').count(),
            1,
        )
