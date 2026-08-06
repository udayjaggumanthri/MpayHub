"""Tests for admin wallet adjustment service and API."""
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.core.exceptions import InsufficientBalance
from apps.transactions.models import PassbookEntry
from apps.wallets.models import Wallet, WalletTransaction
from apps.wallet_adjustments.exceptions import WalletAdjustmentError
from apps.wallet_adjustments.models import WalletAdjustment
from apps.wallet_adjustments.services import apply_wallet_adjustment


def _make_user(*, phone, email, role, user_id, first_name='Test', last_name='User'):
    return User.objects.create_user(
        phone=phone,
        email=email,
        password='TestPass123!',
        role=role,
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
    )


class WalletAdjustmentServiceTests(TestCase):
    def setUp(self):
        self.admin = _make_user(
            phone='9000000001',
            email='adj.admin@example.com',
            role='Admin',
            user_id='ADJADM1',
            first_name='Adj',
            last_name='Admin',
        )
        self.target = _make_user(
            phone='9000000002',
            email='adj.target@example.com',
            role='Retailer',
            user_id='ADJRET1',
            first_name='Adj',
            last_name='Retailer',
        )
        self.main = Wallet.get_wallet(self.target, 'main')
        self.main.credit(Decimal('1000.0000'), reference='SEED', description='seed')
        self.main.refresh_from_db()

    def _base_kwargs(self, **overrides):
        data = {
            'admin_user': self.admin,
            'target_user': self.target,
            'wallet_type': 'main',
            'adjustment_type': 'CREDIT',
            'amount': Decimal('100.0000'),
            'reference_number': 'TXN-REF-001',
            'reason_category': 'failed_transaction',
            'remarks': 'Correcting failed pay-in that did not credit.',
        }
        data.update(overrides)
        return data

    def test_credit_updates_balance_passbook_and_audit(self):
        before = Wallet.get_wallet(self.target, 'main').balance
        adj = apply_wallet_adjustment(**self._base_kwargs())
        wallet = Wallet.get_wallet(self.target, 'main')
        self.assertEqual(wallet.balance, before + Decimal('100.0000'))
        self.assertEqual(adj.status, 'SUCCESS')
        self.assertEqual(adj.balance_before, before)
        self.assertEqual(adj.balance_after, wallet.balance)
        self.assertTrue(adj.adjustment_id.startswith('ADJ-'))
        self.assertEqual(adj.adjusted_by_id, self.admin.id)
        self.assertTrue(adj.adjusted_by_name)

        pb = PassbookEntry.objects.filter(service='wallet_adjustment', service_id=adj.adjustment_id).first()
        self.assertIsNotNone(pb)
        self.assertEqual(pb.credit_amount, Decimal('100.0000'))
        self.assertEqual(pb.debit_amount, Decimal('0'))
        self.assertEqual(pb.wallet_type, 'main')

        self.assertIsNotNone(adj.wallet_transaction_id)
        wt = WalletTransaction.objects.get(pk=adj.wallet_transaction_id)
        self.assertEqual(wt.transaction_type, 'credit')
        self.assertEqual(wt.amount, Decimal('100.0000'))

    def test_debit_updates_balance(self):
        before = Wallet.get_wallet(self.target, 'main').balance
        adj = apply_wallet_adjustment(
            **self._base_kwargs(
                adjustment_type='DEBIT',
                amount=Decimal('250.0000'),
                reference_number='TXN-REF-DEBIT',
            )
        )
        wallet = Wallet.get_wallet(self.target, 'main')
        self.assertEqual(wallet.balance, before - Decimal('250.0000'))
        self.assertEqual(adj.adjustment_type, 'DEBIT')
        pb = PassbookEntry.objects.get(service_id=adj.adjustment_id)
        self.assertEqual(pb.debit_amount, Decimal('250.0000'))
        self.assertEqual(pb.credit_amount, Decimal('0'))

    def test_debit_insufficient_balance(self):
        with self.assertRaises(InsufficientBalance):
            apply_wallet_adjustment(
                **self._base_kwargs(
                    adjustment_type='DEBIT',
                    amount=Decimal('99999.0000'),
                    reference_number='TXN-REF-INSF',
                )
            )
        self.assertEqual(WalletAdjustment.objects.count(), 0)

    def test_missing_remarks_rejected(self):
        with self.assertRaises(WalletAdjustmentError) as ctx:
            apply_wallet_adjustment(**self._base_kwargs(remarks='hi'))
        self.assertEqual(ctx.exception.code, 'REMARKS_REQUIRED')

    def test_missing_reference_rejected(self):
        with self.assertRaises(WalletAdjustmentError) as ctx:
            apply_wallet_adjustment(**self._base_kwargs(reference_number='  '))
        self.assertEqual(ctx.exception.code, 'REFERENCE_REQUIRED')

    def test_duplicate_reference_rejected(self):
        apply_wallet_adjustment(**self._base_kwargs(reference_number='SAME-REF'))
        with self.assertRaises(WalletAdjustmentError) as ctx:
            apply_wallet_adjustment(
                **self._base_kwargs(reference_number='SAME-REF', amount=Decimal('10.0000'))
            )
        self.assertEqual(ctx.exception.code, 'DUPLICATE_REFERENCE')

    @override_settings(WALLET_ADJUSTMENT_MAX_AMOUNT=50)
    def test_max_amount_cap(self):
        with self.assertRaises(WalletAdjustmentError) as ctx:
            apply_wallet_adjustment(**self._base_kwargs(amount=Decimal('51.0000')))
        self.assertEqual(ctx.exception.code, 'AMOUNT_CAP_EXCEEDED')

    def test_bbps_wallet_allowed(self):
        bbps = Wallet.get_wallet(self.target, 'bbps')
        before = Decimal(str(bbps.balance))
        adj = apply_wallet_adjustment(
            **self._base_kwargs(
                wallet_type='bbps',
                reference_number='BBPS-REF-1',
                amount=Decimal('75.0000'),
            )
        )
        bbps.refresh_from_db()
        self.assertEqual(Decimal(str(bbps.balance)), before + Decimal('75.0000'))
        self.assertEqual(adj.wallet_type, 'bbps')

    def test_commission_wallet_rejected(self):
        with self.assertRaises(WalletAdjustmentError) as ctx:
            apply_wallet_adjustment(**self._base_kwargs(wallet_type='commission'))
        self.assertEqual(ctx.exception.code, 'INVALID_WALLET_TYPE')


class WalletAdjustmentAPITests(TestCase):
    def setUp(self):
        self.admin = _make_user(
            phone='9000000011',
            email='adj.api.admin@example.com',
            role='Admin',
            user_id='ADJAPIADM',
            first_name='Api',
            last_name='Admin',
        )
        self.retailer = _make_user(
            phone='9000000012',
            email='adj.api.ret@example.com',
            role='Retailer',
            user_id='ADJAPIRET',
            first_name='Api',
            last_name='Retailer',
        )
        Wallet.get_wallet(self.retailer, 'main').credit(
            Decimal('500.0000'), reference='SEED', description='seed'
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin)
        self.retailer_client = APIClient()
        self.retailer_client.force_authenticate(user=self.retailer)

    def test_non_admin_forbidden(self):
        resp = self.retailer_client.post(
            '/api/admin/wallet-adjustments/',
            {
                'user_id': self.retailer.id,
                'wallet_type': 'main',
                'adjustment_type': 'CREDIT',
                'amount': '10.0000',
                'reference_number': 'NOPE',
                'reason_category': 'other',
                'remarks': 'Should not work for retailers',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_create_and_list(self):
        resp = self.admin_client.post(
            '/api/admin/wallet-adjustments/',
            {
                'user_id': self.retailer.id,
                'wallet_type': 'main',
                'adjustment_type': 'CREDIT',
                'amount': '25.5000',
                'reference_number': 'API-REF-1',
                'reason_category': 'amount_not_reflected',
                'remarks': 'Debited but not reflected — correcting.',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['data']['adjustment']['adjustment_type'], 'CREDIT')
        self.assertIn('ADJ-', body['data']['adjustment']['adjustment_id'])

        listed = self.admin_client.get('/api/admin/wallet-adjustments/')
        self.assertEqual(listed.status_code, 200)
        data = listed.json()['data']
        self.assertGreaterEqual(data['pagination']['total'], 1)
        self.assertTrue(any(r['reference_number'] == 'API-REF-1' for r in data['results']))

    def test_user_lookup_returns_balances(self):
        resp = self.admin_client.get('/api/admin/wallet-adjustments/user-lookup/', {'q': '9000000012'})
        self.assertEqual(resp.status_code, 200)
        users = resp.json()['data']['users']
        self.assertEqual(len(users), 1)
        self.assertIn('main', users[0]['balances'])
        self.assertIn('bbps', users[0]['balances'])

    def test_export_xlsx(self):
        apply_wallet_adjustment(
            admin_user=self.admin,
            target_user=self.retailer,
            wallet_type='main',
            adjustment_type='DEBIT',
            amount=Decimal('5.0000'),
            reference_number='EXPORT-REF',
            reason_category='other',
            remarks='Export smoke test adjustment.',
        )
        resp = self.admin_client.get('/api/admin/wallet-adjustments/export.xlsx')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            'spreadsheetml',
            resp.get('Content-Type', ''),
        )
        self.assertTrue(len(resp.content) > 100)
