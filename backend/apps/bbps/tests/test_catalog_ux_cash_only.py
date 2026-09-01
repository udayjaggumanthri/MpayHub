"""Tests for BBPS catalog UX cash-only mode."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.bbps.models import (
    BbpsBillerMaster,
    BbpsBillerPaymentChannelLimit,
    BbpsBillerPaymentModeLimit,
    BbpsCatalogUxSettings,
)
from apps.bbps.services import get_biller_payment_ui_options, get_billers_by_category
from apps.bbps.service_flow.compliance import enforce_biller_mode_channel_constraints
from apps.core.exceptions import TransactionFailed

User = get_user_model()


@override_settings(BBPS_ACTIVE_ENVIRONMENT='uat')
class BbpsCatalogUxCashOnlyTests(TestCase):
    def setUp(self):
        from apps.bbps.service_flow.catalog_ux_settings import _cached_cash_only_for_users
        from apps.bbps.service_flow.provider_policy import clear_provider_policy_cache

        cache.clear()
        clear_provider_policy_cache()
        _cached_cash_only_for_users.cache_clear()

        BbpsCatalogUxSettings.objects.create(environment='uat', cash_only_for_users=True)

        self.cash_biller = BbpsBillerMaster.objects.create(
            environment='uat',
            biller_id='CASHBILL01',
            biller_name='Cash Capable',
            biller_category='Credit Card',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        BbpsBillerPaymentChannelLimit.objects.create(
            biller=self.cash_biller, payment_channel='AGT', min_amount=0, max_amount=0
        )
        BbpsBillerPaymentModeLimit.objects.create(
            biller=self.cash_biller, payment_mode='Cash', min_amount=0, max_amount=0
        )

        self.int_only = BbpsBillerMaster.objects.create(
            environment='uat',
            biller_id='INTONLY01',
            biller_name='Internet Only',
            biller_category='Credit Card',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        BbpsBillerPaymentChannelLimit.objects.create(
            biller=self.int_only, payment_channel='INT', min_amount=0, max_amount=0
        )
        BbpsBillerPaymentModeLimit.objects.create(
            biller=self.int_only, payment_mode='UPI', min_amount=0, max_amount=0
        )

        self.hdfc_like = BbpsBillerMaster.objects.create(
            environment='uat',
            biller_id='HDFC00000NATW1',
            biller_name='HDFC Credit Card',
            biller_category='Credit Card',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        for ch in ('ATM', 'INT', 'MOB'):
            BbpsBillerPaymentChannelLimit.objects.create(
                biller=self.hdfc_like, payment_channel=ch, min_amount=0, max_amount=0
            )
        for mode in ('Debit Card', 'Internet Banking', 'UPI'):
            BbpsBillerPaymentModeLimit.objects.create(
                biller=self.hdfc_like, payment_mode=mode, min_amount=0, max_amount=0
            )

        self.empty_limits = BbpsBillerMaster.objects.create(
            environment='uat',
            biller_id='EMPTYLIM01',
            biller_name='No Limits',
            biller_category='Credit Card',
            biller_status='ACTIVE',
            is_active_local=True,
        )

    def test_get_billers_filters_non_cash_capable(self):
        rows = get_billers_by_category('credit-card')
        ids = {r['biller_id'] for r in rows}
        self.assertIn('CASHBILL01', ids)
        self.assertNotIn('INTONLY01', ids)

    def test_hdfc_like_biller_hidden_in_cash_only(self):
        rows = get_billers_by_category('credit-card')
        ids = {r['biller_id'] for r in rows}
        self.assertNotIn('HDFC00000NATW1', ids)

    def test_empty_limits_not_cash_capable(self):
        rows = get_billers_by_category('credit-card')
        ids = {r['biller_id'] for r in rows}
        self.assertNotIn('EMPTYLIM01', ids)

    def test_payment_ui_forces_cash_only(self):
        out = get_biller_payment_ui_options('CASHBILL01')
        self.assertEqual(out['payment_modes'], ['Cash'])
        self.assertTrue(out['hide_payment_method'])
        self.assertEqual(out['payment_ui_mode'], 'cash_only_assisted')

    def test_payment_ui_no_fake_cash_when_not_capable(self):
        out = get_biller_payment_ui_options('HDFC00000NATW1')
        self.assertEqual(out['payment_modes'], [])
        self.assertEqual(out['source'], 'requires_device_context')
        self.assertFalse(out['hide_payment_method'])
        self.assertEqual(out['payment_ui_mode'], 'standard')

    def test_enforce_rejects_non_cash_mode(self):
        with self.assertRaises(TransactionFailed):
            enforce_biller_mode_channel_constraints(
                biller=self.cash_biller,
                payment_mode='UPI',
                payment_channel='AGT',
                amount='100',
            )

    def test_get_bill_categories_only_lists_cash_capable_categories(self):
        from apps.bbps.services import get_bill_categories

        BbpsBillerMaster.objects.create(
            environment='uat',
            biller_id='ELECINT01',
            biller_name='Electric INT only',
            biller_category='Electricity',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        elec = BbpsBillerMaster.objects.get(biller_id='ELECINT01', environment='uat')
        BbpsBillerPaymentChannelLimit.objects.create(
            biller=elec, payment_channel='INT', min_amount=0, max_amount=0
        )
        BbpsBillerPaymentModeLimit.objects.create(
            biller=elec, payment_mode='UPI', min_amount=0, max_amount=0
        )
        cache.clear()
        cats = {c['id'] for c in get_bill_categories()}
        self.assertIn('credit-card', cats)
        self.assertNotIn('electricity', cats)

    @patch('apps.bbps.views._invalidate_bbps_user_catalog_cache')
    def test_toggle_invalidates_cache(self, mock_invalidate):
        admin = User.objects.create_user(
            phone='9555555577',
            email='cash-toggle@test.com',
            password='secret123',
            role='Admin',
            user_id='CASHTOG1',
        )
        client = APIClient()
        client.force_authenticate(user=admin)
        cache.set('bbps:categories:uat:cash_only=1', [{'id': 'stale'}], timeout=3600)
        r = client.patch(
            '/api/bbps/admin/catalog-ux-settings/',
            {'environment': 'uat', 'cash_only_for_users': True},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        mock_invalidate.assert_called_once()
