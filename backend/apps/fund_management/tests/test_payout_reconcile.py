"""Tests for admin payout recovery (stuck PENDING reconcile)."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.bank_accounts.models import BankAccount
from apps.fund_management.models import Payout
from apps.fund_management.payout_reconcile import (
    admin_mark_payout_failed,
    admin_mark_payout_success,
)
from apps.wallets.models import Wallet

User = get_user_model()


class PayoutReconcileTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9000000001',
            email='admin_rec@test.com',
            password='pass12345',
            role='Admin',
            user_id='AREC01',
            first_name='Admin',
            last_name='Rec',
        )
        self.user = User.objects.create_user(
            phone='9000000002',
            email='retailer_rec@test.com',
            password='pass12345',
            role='Retailer',
            user_id='RREC01',
            first_name='Retail',
            last_name='User',
        )
        self.wallet = Wallet.get_wallet(self.user, 'main')
        self.wallet.balance = Decimal('5000.0000')
        self.wallet.held_balance = Decimal('0')
        self.wallet.save(update_fields=['balance', 'held_balance'])
        self.bank = BankAccount.objects.create(
            user=self.user,
            account_number='1234567890',
            ifsc='HDFC0000516',
            bank_name='HDFC Bank',
            account_holder_name='Retail User',
            beneficiary_name='Retail User',
            is_verified=True,
        )
        self.payout = Payout.objects.create(
            user=self.user,
            bank_account=self.bank,
            amount=Decimal('100.0000'),
            charge=Decimal('7.0000'),
            platform_fee=Decimal('0'),
            total_deducted=Decimal('107.0000'),
            transfer_mode='IMPS',
            status='PENDING',
            transaction_id='POTSTREC001',
            merchant_ref_id='POTSTREC001',
            provider_code='vimopay',
        )
        self.wallet.held_balance = Decimal('107.0000')
        self.wallet.save(update_fields=['held_balance'])

    def test_mark_success_settles_hold(self):
        updated = admin_mark_payout_success(
            payout=self.payout,
            actor=self.admin,
            rrn='RRN123',
            internal_note='Confirmed paid on Vidual dashboard',
        )
        self.assertEqual(updated.status, 'SUCCESS')
        self.assertEqual(updated.rrn, 'RRN123')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.held_balance, Decimal('0.0000'))
        self.assertEqual(self.wallet.balance, Decimal('4893.0000'))

    def test_mark_failed_releases_hold(self):
        updated = admin_mark_payout_failed(
            payout=self.payout,
            actor=self.admin,
            reason='Bank rejected',
            internal_note='Vidual shows failed',
        )
        self.assertEqual(updated.status, 'FAILED')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.held_balance, Decimal('0.0000'))
        self.assertEqual(self.wallet.balance, Decimal('5000.0000'))

    def test_requires_note(self):
        with self.assertRaises(ValidationError):
            admin_mark_payout_success(
                payout=self.payout,
                actor=self.admin,
                internal_note='ok',
            )

    def test_admin_api_list_and_actions(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.get('/api/admin/payout-recovery/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get('success'))
        self.assertGreaterEqual(res.data['data']['total'], 1)

        stats = client.get('/api/admin/payout-recovery/stats/')
        self.assertEqual(stats.status_code, 200)
        self.assertGreaterEqual(stats.data['data']['pending_count'], 1)

        fail = client.post(
            f'/api/admin/payout-recovery/{self.payout.id}/mark-failed/',
            {'internal_note': 'Provider confirmed failure', 'reason': 'failed at bank'},
            format='json',
        )
        self.assertEqual(fail.status_code, 200)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, 'FAILED')
