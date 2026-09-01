"""Admin catalog visibility: cash-only apply, enable guards, API surfaces."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.bbps.models import (
    BbpsBillerMaster,
    BbpsBillerPaymentChannelLimit,
    BbpsBillerPaymentModeLimit,
    BbpsCatalogUxSettings,
)
from apps.bbps.service_flow.catalog_visibility import (
    HOLD_ADMIN,
    HOLD_CASH_ONLY,
    apply_cash_only_visibility_for_env,
    assert_biller_can_be_enabled,
    catalog_visibility_summary,
    hidden_billers_queryset,
    invalidate_catalog_visibility_summary_cache,
    preview_cash_only_toggle,
)
from apps.bbps.service_flow.catalog_ux_settings import (
    _cached_cash_only_for_users,
    update_catalog_ux_settings,
)

User = get_user_model()


class CatalogVisibilityAdminTests(TestCase):
    def setUp(self):
        _cached_cash_only_for_users.cache_clear()
        BbpsCatalogUxSettings.objects.create(environment='uat', cash_only_for_users=True)

    def _hdfc_like(self, biller_id='HDFC_TEST'):
        biller = BbpsBillerMaster.objects.create(
            biller_id=biller_id,
            biller_name='HDFC Credit Card',
            biller_category='credit card',
            biller_status='ACTIVE',
            environment='uat',
        )
        for ch in ('ATM', 'INT', 'MOB'):
            BbpsBillerPaymentChannelLimit.objects.create(
                biller=biller, payment_channel=ch, min_amount=0, max_amount=0
            )
        for mode in ('Debit Card', 'Internet Banking', 'UPI'):
            BbpsBillerPaymentModeLimit.objects.create(
                biller=biller, payment_mode=mode, min_amount=0, max_amount=0
            )
        return biller

    def _cash_capable(self, biller_id='CASH_OK'):
        biller = BbpsBillerMaster.objects.create(
            biller_id=biller_id,
            biller_name='Cash Biller',
            biller_category='electricity',
            biller_status='ACTIVE',
            environment='uat',
        )
        BbpsBillerPaymentChannelLimit.objects.create(
            biller=biller, payment_channel='AGT', min_amount=0, max_amount=0
        )
        BbpsBillerPaymentModeLimit.objects.create(
            biller=biller, payment_mode='Cash', min_amount=0, max_amount=0
        )
        return biller

    def test_hdfc_like_auto_hidden_on_apply(self):
        biller = self._hdfc_like()
        stats = apply_cash_only_visibility_for_env('uat')
        biller.refresh_from_db()
        self.assertGreaterEqual(stats['hidden'], 1)
        self.assertFalse(biller.is_active_local)
        self.assertEqual(biller.local_visibility_hold, HOLD_CASH_ONLY)

    def test_admin_disabled_not_overwritten(self):
        biller = self._hdfc_like('HDFC_ADMIN')
        biller.is_active_local = False
        biller.local_visibility_hold = HOLD_ADMIN
        biller.save(update_fields=['is_active_local', 'local_visibility_hold', 'updated_at'])
        stats = apply_cash_only_visibility_for_env('uat')
        biller.refresh_from_db()
        self.assertGreaterEqual(stats['skipped_admin'], 1)
        self.assertEqual(biller.local_visibility_hold, HOLD_ADMIN)

    def test_cash_only_off_restores_policy_hold_only(self):
        hdfc = self._hdfc_like('HDFC_RESTORE')
        cash = self._cash_capable()
        apply_cash_only_visibility_for_env('uat')
        hdfc.refresh_from_db()
        self.assertEqual(hdfc.local_visibility_hold, HOLD_CASH_ONLY)
        BbpsCatalogUxSettings.objects.filter(environment='uat').update(cash_only_for_users=False)
        _cached_cash_only_for_users.cache_clear()
        stats = apply_cash_only_visibility_for_env('uat')
        hdfc.refresh_from_db()
        cash.refresh_from_db()
        self.assertGreaterEqual(stats['restored'], 1)
        self.assertTrue(hdfc.is_active_local)
        self.assertEqual(hdfc.local_visibility_hold, '')
        self.assertTrue(cash.is_active_local)

    def test_enable_blocked_when_cash_only_ineligible(self):
        biller = self._hdfc_like('HDFC_BLOCK')
        apply_cash_only_visibility_for_env('uat')
        biller.refresh_from_db()
        msg = assert_biller_can_be_enabled(biller)
        self.assertIsNotNone(msg)

    def test_preview_counts_match_apply(self):
        self._hdfc_like('HDFC_PREV')
        self._cash_capable('CASH_PREV')
        preview = preview_cash_only_toggle('uat', cash_only_for_users=True)
        stats = apply_cash_only_visibility_for_env('uat')
        self.assertGreaterEqual(preview['would_hide_count'], 1)
        self.assertGreaterEqual(stats['hidden'], 1)

    def test_update_catalog_ux_settings_runs_apply(self):
        self._hdfc_like('HDFC_PATCH')
        out = update_catalog_ux_settings(environment='uat', cash_only_for_users=True)
        self.assertIn('apply_stats', out)
        row = BbpsBillerMaster.objects.get(biller_id='HDFC_PATCH')
        self.assertEqual(row.local_visibility_hold, HOLD_CASH_ONLY)

    def test_hidden_endpoint_uses_sql_pagination(self):
        self._hdfc_like('HIDDEN_A')
        cash = self._cash_capable('VISIBLE_A')
        cash.is_active_local = True
        cash.save(update_fields=['is_active_local', 'updated_at'])
        apply_cash_only_visibility_for_env('uat')
        admin = User.objects.create_user(
            phone='9555555588',
            email='hidden-api@test.com',
            password='secret123',
            role='Admin',
            user_id='HIDAPI1',
        )
        client = APIClient()
        client.force_authenticate(user=admin)
        res = client.get('/api/bbps/admin/catalog-visibility/hidden/', {'environment': 'uat', 'page_size': 1})
        self.assertEqual(res.status_code, 200)
        data = res.json()['data']
        self.assertGreaterEqual(data['pagination']['total'], 1)
        self.assertEqual(len(data['billers']), 1)

    def test_summary_endpoint_uses_cache(self):
        self._cash_capable('CACHE_SUM')
        cache.clear()
        first = catalog_visibility_summary('uat')
        second = catalog_visibility_summary('uat')
        self.assertEqual(first['partner_visible'], second['partner_visible'])
        cache_key = 'bbps:catalog_visibility_summary:uat'
        self.assertIsNotNone(cache.get(cache_key))
        invalidate_catalog_visibility_summary_cache('uat')
        self.assertIsNone(cache.get(cache_key))

    def test_partner_view_list_filters_active_local_sql(self):
        visible = self._cash_capable('PARTNER_OK')
        visible.is_active_local = True
        visible.save(update_fields=['is_active_local', 'updated_at'])
        hidden = self._hdfc_like('PARTNER_HIDE')
        apply_cash_only_visibility_for_env('uat')
        admin = User.objects.create_user(
            phone='9555555599',
            email='partner-list@test.com',
            password='secret123',
            role='Admin',
            user_id='PARTL1',
        )
        client = APIClient()
        client.force_authenticate(user=admin)
        res = client.get('/api/bbps/admin/biller-master/', {'view': 'partner', 'environment': 'uat'})
        self.assertEqual(res.status_code, 200)
        biller_ids = {b['biller_id'] for b in res.json()['data']['billers']}
        self.assertIn('PARTNER_OK', biller_ids)
        self.assertNotIn('PARTNER_HIDE', biller_ids)
        self.assertEqual(hidden_billers_queryset('uat').filter(biller_id='PARTNER_HIDE').count(), 1)
