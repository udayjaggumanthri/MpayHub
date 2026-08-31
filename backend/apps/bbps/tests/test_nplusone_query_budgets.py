"""N+1 query budgets for BBPS catalog list paths and admin maps."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.bbps.models import (
    BbpsBillerMaster,
    BbpsBillerPaymentChannelLimit,
    BbpsBillerPaymentModeLimit,
    BbpsCategoryCommissionRule,
    BbpsProviderBillerMap,
    BbpsServiceCategory,
    BbpsServiceProvider,
)
from apps.bbps.service_flow.catalog_ux_settings import _cached_cash_only_for_users
from apps.bbps.service_flow.provider_policy import clear_provider_policy_cache
from apps.bbps.services import get_bill_categories, governance_block_reasons_for_map

User = get_user_model()


@override_settings(BBPS_ACTIVE_ENVIRONMENT='uat')
class BbpsCatalogQueryBudgetTests(TestCase):
    def setUp(self):
        cache.clear()
        clear_provider_policy_cache()
        _cached_cash_only_for_users.cache_clear()

    def _make_visible_biller(self, biller_id: str, category: str = 'Electricity'):
        master = BbpsBillerMaster.objects.create(
            environment='uat',
            biller_id=biller_id,
            biller_name=f'Biller {biller_id}',
            biller_category=category,
            biller_status='ACTIVE',
            is_active_local=True,
        )
        BbpsBillerPaymentChannelLimit.objects.create(
            biller=master, payment_channel='AGT', min_amount=0, max_amount=0
        )
        BbpsBillerPaymentModeLimit.objects.create(
            biller=master, payment_mode='Cash', min_amount=0, max_amount=0
        )
        return master

    def test_get_bill_categories_query_count_stable_with_more_billers(self):
        for i in range(5):
            self._make_visible_biller(f'CATQ{i:03d}')
        cache.clear()
        clear_provider_policy_cache()
        _cached_cash_only_for_users.cache_clear()

        with CaptureQueriesContext(connection) as ctx5:
            cats5 = get_bill_categories()
        n5 = len(ctx5.captured_queries)
        self.assertTrue(any(c['id'] == 'electricity' for c in cats5))

        for i in range(5, 25):
            self._make_visible_biller(f'CATQ{i:03d}')
        cache.clear()
        clear_provider_policy_cache()
        _cached_cash_only_for_users.cache_clear()

        with CaptureQueriesContext(connection) as ctx25:
            cats25 = get_bill_categories()
        n25 = len(ctx25.captured_queries)
        self.assertTrue(any(c['id'] == 'electricity' for c in cats25))
        # Query count must not grow with biller count (batch prefetch + policy cache).
        self.assertLessEqual(n25, n5 + 2, f'n5={n5} n25={n25}')
        self.assertLessEqual(n25, 20)

    def test_get_bill_categories_cache_hit(self):
        self._make_visible_biller('CACHE01')
        cache.clear()
        clear_provider_policy_cache()
        _cached_cash_only_for_users.cache_clear()
        first = get_bill_categories()
        # Second call: categories payload cached; env/cash_only may still resolve cheaply.
        with CaptureQueriesContext(connection) as ctx:
            second = get_bill_categories()
        self.assertEqual(first, second)
        self.assertLessEqual(len(ctx.captured_queries), 5)


@override_settings(BBPS_PROVIDER_GOVERNANCE_ENABLED=True)
class ProviderBillerMapsQueryBudgetTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9555555588',
            email='maps-budget@test.com',
            password='secret123',
            role='Admin',
            user_id='MAPBUD1',
        )
        self.cat = BbpsServiceCategory.objects.create(code='electricity', name='Electricity', is_active=True)
        BbpsCategoryCommissionRule.objects.create(
            category=self.cat,
            rule_code='default',
            is_active=True,
            value=0,
        )
        self.provider = BbpsServiceProvider.objects.create(
            category=self.cat,
            code='elec-op',
            name='Elec OP',
            is_active=True,
        )
        for i in range(12):
            biller = BbpsBillerMaster.objects.create(
                biller_id=f'MAPB{i:03d}',
                biller_name=f'Map Biller {i}',
                biller_category='Electricity',
                biller_status='ACTIVE',
                is_active_local=True,
            )
            BbpsProviderBillerMap.objects.create(
                provider=self.provider,
                biller_master=biller,
                is_active=True,
            )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_provider_biller_maps_list_batches_commission_rule_lookup(self):
        """Maps + rules batch only — not 1 exists() per map."""
        self.client.get('/api/bbps/admin/provider-biller-maps/')
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get('/api/bbps/admin/provider-biller-maps/')
        self.assertEqual(r.status_code, 200, r.content)
        maps = r.json()['data']['maps']
        self.assertGreaterEqual(len(maps), 12)
        for entry in maps:
            self.assertNotIn('no_rule', entry.get('blocked_by') or [])
        self.assertLessEqual(len(ctx.captured_queries), 4)

    def test_governance_block_reasons_uses_preloaded_ids(self):
        from apps.bbps.services import _active_commission_category_ids

        row = (
            BbpsProviderBillerMap.objects.filter(is_deleted=False)
            .select_related('provider__category', 'biller_master')
            .first()
        )
        ids = _active_commission_category_ids()
        with CaptureQueriesContext(connection) as ctx:
            reasons = governance_block_reasons_for_map(row, categories_with_rules=ids)
        self.assertEqual(len(ctx.captured_queries), 0)
        self.assertNotIn('no_rule', reasons)
