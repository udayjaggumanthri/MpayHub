from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from apps.core.financial_access import assert_can_perform_financial_txn, user_may_perform_financial_txn
from apps.admin_panel.models import PayoutSlabConfig
from apps.fund_management.models import PayInPackage, PayoutSlabTier, UserPackageAssignment
from apps.fund_management.payin_distribution import _compute_payin_distribution
from apps.fund_management.services import (
    max_payout_eligible_for_user,
    payout_slab_charge,
    payout_slab_charge_for_user,
    resolve_payout_package,
)
from apps.users.models import UserHierarchy
from apps.wallets.models import Wallet
from apps.wallets.services import transfer_main_to_bbps

User = get_user_model()


class PayoutSlabChargeTests(TestCase):
    def test_low_slab_inclusive(self):
        self.assertEqual(payout_slab_charge(Decimal('24999')), Decimal('7'))

    def test_high_slab(self):
        self.assertEqual(payout_slab_charge(Decimal('25000')), Decimal('15'))

    def test_admin_config_overrides_default_slabs(self):
        PayoutSlabConfig.objects.create(
            name='test-config',
            low_max_amount=Decimal('10000'),
            low_charge=Decimal('5'),
            high_charge=Decimal('11'),
            is_active=True,
        )
        self.assertEqual(payout_slab_charge(Decimal('10000')), Decimal('5.0000'))
        self.assertEqual(payout_slab_charge(Decimal('10001')), Decimal('11.0000'))


def _make_pay_package(code, sort_order=0):
    return PayInPackage.objects.create(
        code=code,
        display_name=code,
        provider='mock',
        gateway_fee_pct=Decimal('1.0000'),
        admin_pct=Decimal('0.2400'),
        super_distributor_pct=Decimal('0.0100'),
        master_distributor_pct=Decimal('0.0200'),
        distributor_pct=Decimal('0.0300'),
        retailer_commission_pct=Decimal('0.0000'),
        sort_order=sort_order,
        is_default=False,
    )


class PayoutSlabPerPackageTests(TestCase):
    """Per-package tiers via assignment; first accessible package wins; empty tiers → global."""

    def setUp(self):
        self.user = User.objects.create_user(
            phone='9444444401',
            email='payout_pkg@test.com',
            password='testpass123',
            role='Retailer',
            user_id='RTPO1',
            first_name='P',
            last_name='User',
        )

    def test_multi_tier_flat_charge(self):
        pkg = _make_pay_package('tiered-pkg')
        PayoutSlabTier.objects.create(
            package=pkg,
            sort_order=0,
            min_amount=Decimal('0'),
            max_amount=Decimal('1000.0000'),
            flat_charge=Decimal('1'),
        )
        PayoutSlabTier.objects.create(
            package=pkg,
            sort_order=1,
            min_amount=Decimal('1000.0001'),
            max_amount=Decimal('5000.0000'),
            flat_charge=Decimal('3'),
        )
        PayoutSlabTier.objects.create(
            package=pkg,
            sort_order=2,
            min_amount=Decimal('5000.0001'),
            max_amount=None,
            flat_charge=Decimal('5'),
        )
        UserPackageAssignment.objects.create(user=self.user, package=pkg)

        self.assertEqual(payout_slab_charge_for_user(self.user, Decimal('500')), Decimal('1.0000'))
        self.assertEqual(payout_slab_charge_for_user(self.user, Decimal('3000')), Decimal('3.0000'))
        self.assertEqual(payout_slab_charge_for_user(self.user, Decimal('10000')), Decimal('5.0000'))

    def test_first_accessible_package_wins_for_payout(self):
        pkg_a = _make_pay_package('payout-first', sort_order=0)
        pkg_b = _make_pay_package('payout-second', sort_order=5)
        PayoutSlabTier.objects.create(
            package=pkg_a,
            sort_order=0,
            min_amount=Decimal('0'),
            max_amount=None,
            flat_charge=Decimal('99'),
        )
        PayoutSlabTier.objects.create(
            package=pkg_b,
            sort_order=0,
            min_amount=Decimal('0'),
            max_amount=None,
            flat_charge=Decimal('1'),
        )
        UserPackageAssignment.objects.create(user=self.user, package=pkg_b)
        UserPackageAssignment.objects.create(user=self.user, package=pkg_a)

        resolved = resolve_payout_package(self.user)
        self.assertEqual(resolved.id, pkg_a.id)
        self.assertEqual(payout_slab_charge_for_user(self.user, Decimal('100')), Decimal('99.0000'))

    def test_no_tiers_on_package_falls_back_to_global_config(self):
        PayoutSlabConfig.objects.filter(is_active=True).update(is_active=False)
        PayoutSlabConfig.objects.create(
            name='fallback-only',
            low_max_amount=Decimal('5000'),
            low_charge=Decimal('2'),
            high_charge=Decimal('8'),
            is_active=True,
        )
        pkg = _make_pay_package('no-tiers')
        UserPackageAssignment.objects.create(user=self.user, package=pkg)

        self.assertEqual(payout_slab_charge_for_user(self.user, Decimal('5000')), Decimal('2.0000'))
        self.assertEqual(payout_slab_charge_for_user(self.user, Decimal('5001')), Decimal('8.0000'))

    def test_max_payout_eligible_for_user_multi_tier(self):
        pkg = _make_pay_package('max-elig')
        PayoutSlabTier.objects.create(
            package=pkg,
            sort_order=0,
            min_amount=Decimal('0'),
            max_amount=Decimal('100.0000'),
            flat_charge=Decimal('10'),
        )
        PayoutSlabTier.objects.create(
            package=pkg,
            sort_order=1,
            min_amount=Decimal('100.0001'),
            max_amount=Decimal('1000.0000'),
            flat_charge=Decimal('20'),
        )
        PayoutSlabTier.objects.create(
            package=pkg,
            sort_order=2,
            min_amount=Decimal('1000.0001'),
            max_amount=None,
            flat_charge=Decimal('30'),
        )
        UserPackageAssignment.objects.create(user=self.user, package=pkg)

        self.assertEqual(max_payout_eligible_for_user(self.user, Decimal('1000')), Decimal('980.0000'))
        self.assertEqual(max_payout_eligible_for_user(self.user, Decimal('150')), Decimal('130.0000'))


class SuperDistributorFinancialBlockTests(TestCase):
    def setUp(self):
        self.sd = User.objects.create_user(
            phone='9111111111',
            email='sd_block@test.com',
            password='testpass123',
            role='Super Distributor',
            user_id='SDT1',
            first_name='S',
            last_name='D',
        )
        self.retailer = User.objects.create_user(
            phone='9111111112',
            email='rt_block@test.com',
            password='testpass123',
            role='Retailer',
            user_id='RTT1',
            first_name='R',
            last_name='T',
        )
        self.admin = User.objects.create_user(
            phone='9111111113',
            email='adm_block@test.com',
            password='testpass123',
            role='Admin',
            user_id='ADM1',
            first_name='A',
            last_name='D',
        )

    def test_sd_may_not_transact(self):
        self.assertFalse(user_may_perform_financial_txn(self.sd))
        with self.assertRaises(PermissionDenied):
            assert_can_perform_financial_txn(self.sd)

    def test_retailer_may_transact(self):
        self.assertTrue(user_may_perform_financial_txn(self.retailer))

    def test_admin_may_not_transact(self):
        self.assertFalse(user_may_perform_financial_txn(self.admin))
        with self.assertRaises(PermissionDenied):
            assert_can_perform_financial_txn(self.admin)


class MainToBbpsTransferTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9222222222',
            email='bbps_tr@test.com',
            password='testpass123',
            role='Retailer',
            user_id='RTT2',
            first_name='A',
            last_name='B',
        )
        self.user.set_mpin('123456')
        Wallet.objects.create(user=self.user, wallet_type='main', balance=Decimal('100.00'))
        Wallet.objects.create(user=self.user, wallet_type='commission', balance=Decimal('0'))
        Wallet.objects.create(user=self.user, wallet_type='bbps', balance=Decimal('0'))

    def test_transfer_moves_balance(self):
        out = transfer_main_to_bbps(self.user, Decimal('40.00'))
        self.assertIn('service_id', out)
        main = Wallet.objects.get(user=self.user, wallet_type='main')
        bbps = Wallet.objects.get(user=self.user, wallet_type='bbps')
        self.assertEqual(main.balance, Decimal('60.00'))
        self.assertEqual(bbps.balance, Decimal('40.00'))


class SuperDistributorOnboardingMatrixTests(TestCase):
    def test_sd_cannot_create_master_distributor(self):
        allowed = UserHierarchy._ROLE_CREATE_MATRIX.get('Super Distributor', [])
        self.assertNotIn('Master Distributor', allowed)
        self.assertIn('Distributor', allowed)
        self.assertIn('Retailer', allowed)


class PayinSelfRoleSliceRollupTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9333333301',
            email='admin_rollup@test.com',
            password='testpass123',
            role='Admin',
            user_id='ADROLL1',
            first_name='Admin',
            last_name='Root',
        )
        self.sd = User.objects.create_user(
            phone='9333333302',
            email='sd_rollup@test.com',
            password='testpass123',
            role='Super Distributor',
            user_id='SDROLL1',
            first_name='Super',
            last_name='Partner',
        )
        self.md = User.objects.create_user(
            phone='9333333303',
            email='md_rollup@test.com',
            password='testpass123',
            role='Master Distributor',
            user_id='MDROLL1',
            first_name='Master',
            last_name='Partner',
        )
        self.dt = User.objects.create_user(
            phone='9333333304',
            email='dt_rollup@test.com',
            password='testpass123',
            role='Distributor',
            user_id='DTROLL1',
            first_name='Distributor',
            last_name='Partner',
        )
        self.retailer = User.objects.create_user(
            phone='9333333305',
            email='rt_rollup@test.com',
            password='testpass123',
            role='Retailer',
            user_id='RTROLL1',
            first_name='Retail',
            last_name='Partner',
        )
        self.package = PayInPackage.objects.create(
            code='rollup-default',
            display_name='Rollup Default',
            provider='mock',
            gateway_fee_pct=Decimal('1.0000'),
            admin_pct=Decimal('0.2400'),
            super_distributor_pct=Decimal('0.0100'),
            master_distributor_pct=Decimal('0.0200'),
            distributor_pct=Decimal('0.0300'),
            retailer_commission_pct=Decimal('0.0000'),
        )
        self.gross = Decimal('100000.0000')

    def _link(self, parent, child):
        UserHierarchy.objects.create(parent_user=parent, child_user=child)

    def _assert_net_invariants(self, dist):
        self.assertEqual(self.gross, dist['net_credit'] + dist['total_deduction'])
        self.assertEqual(
            dist['total_deduction'],
            dist['gw'] + dist['ad_total'] + dist['sd_payout'] + dist['md_payout'] + dist['dt_payout'],
        )

    def test_admin_to_distributor_direct_onboarding_credits_distributor_slice(self):
        self._link(self.admin, self.dt)
        dist = _compute_payin_distribution(self.package, self.gross, self.dt)

        self.assertEqual(dist['dt_user'], self.dt)
        self.assertEqual(dist['dt_payout'], Decimal('30.0000'))
        self.assertEqual(dist['md_payout'], Decimal('0.0000'))
        self.assertEqual(dist['sd_payout'], Decimal('0.0000'))
        self.assertEqual(dist['absorbed'], Decimal('30.0000'))
        self.assertEqual(dist['ad_total'], Decimal('270.0000'))
        self._assert_net_invariants(dist)

    def test_admin_to_master_distributor_direct_onboarding_credits_master_slice(self):
        self._link(self.admin, self.md)
        dist = _compute_payin_distribution(self.package, self.gross, self.md)

        self.assertEqual(dist['md_user'], self.md)
        self.assertEqual(dist['dt_user'], None)
        self.assertEqual(dist['md_payout'], Decimal('50.0000'))
        self.assertEqual(dist['sd_payout'], Decimal('0.0000'))
        self.assertEqual(dist['dt_payout'], Decimal('0.0000'))
        self.assertEqual(dist['absorbed'], Decimal('10.0000'))
        self.assertEqual(dist['ad_total'], Decimal('250.0000'))
        self._assert_net_invariants(dist)

    def test_admin_to_super_distributor_direct_onboarding_credits_super_slice(self):
        self._link(self.admin, self.sd)
        dist = _compute_payin_distribution(self.package, self.gross, self.sd)

        self.assertEqual(dist['sd_user'], self.sd)
        self.assertEqual(dist['sd_payout'], Decimal('60.0000'))
        self.assertEqual(dist['md_payout'], Decimal('0.0000'))
        self.assertEqual(dist['dt_payout'], Decimal('0.0000'))
        self.assertEqual(dist['absorbed'], Decimal('0.0000'))
        self.assertEqual(dist['ad_total'], Decimal('240.0000'))
        self._assert_net_invariants(dist)

    def test_existing_full_chain_distribution_remains_unchanged(self):
        self._link(self.admin, self.sd)
        self._link(self.sd, self.md)
        self._link(self.md, self.dt)
        self._link(self.dt, self.retailer)
        dist = _compute_payin_distribution(self.package, self.gross, self.retailer)

        self.assertEqual(dist['sd_user'], self.sd)
        self.assertEqual(dist['md_user'], self.md)
        self.assertEqual(dist['dt_user'], self.dt)
        self.assertEqual(dist['sd_payout'], Decimal('10.0000'))
        self.assertEqual(dist['md_payout'], Decimal('20.0000'))
        self.assertEqual(dist['dt_payout'], Decimal('30.0000'))
        self.assertEqual(dist['absorbed'], Decimal('0.0000'))
        self.assertEqual(dist['ad_total'], Decimal('240.0000'))
        self._assert_net_invariants(dist)
