"""Tests for pay-in preview hierarchy scenarios."""
from decimal import Decimal

from django.test import TestCase

from apps.fund_management.models import PayInPackage
from apps.fund_management.payin_distribution import (
    build_preview_hierarchy_scenarios,
    compute_payin_for_chain_presence,
)


class PayInPreviewScenarioTests(TestCase):
    def setUp(self):
        self.package = PayInPackage.objects.create(
            code='scenario_pkg',
            display_name='Scenario pkg',
            provider='razorpay',
            gateway_fee_pct=Decimal('1.0000'),
            admin_pct=Decimal('0.24'),
            super_distributor_pct=Decimal('0.01'),
            master_distributor_pct=Decimal('0.02'),
            distributor_pct=Decimal('0.03'),
            min_amount=Decimal('1'),
            max_amount_per_txn=Decimal('200000'),
        )

    def test_admin_direct_retailer_absorbs_chain_to_admin(self):
        result = compute_payin_for_chain_presence(
            self.package,
            Decimal('100000'),
            gateway_fee_pct=Decimal('1'),
            has_super_distributor=False,
            has_master_distributor=False,
            has_distributor=False,
        )
        self.assertGreater(Decimal(result['hierarchy']['absorbed_to_admin']), Decimal('0'))
        self.assertTrue(result['hierarchy']['rollup_steps'])

    def test_build_preview_scenarios_includes_all_presets(self):
        scenarios = build_preview_hierarchy_scenarios(
            self.package, Decimal('100000'), gateway_fee_pct=Decimal('1')
        )
        ids = {s['id'] for s in scenarios}
        self.assertIn('generic', ids)
        self.assertIn('admin_direct_retailer', ids)
        self.assertIn('full_chain', ids)
        self.assertIn('missing_distributor', ids)
