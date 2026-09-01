from django.test import TestCase

from apps.bbps.models import BbpsBillerMaster
from apps.bbps.services import get_bill_categories, get_billers_by_category


class BbpsMobileCategoryRoutingTests(TestCase):
    """Regression: BillAvenue Mobile maps to postpaid; prepaid stays disjoint."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_get_billers_by_category_mobile_postpaid_matches_mobile_biller_category(self):
        BbpsBillerMaster.objects.create(
            biller_id='OTME00000XX243',
            biller_name='OTME',
            biller_category='Mobile',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        rows = get_billers_by_category('mobile-postpaid')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['biller_id'], 'OTME00000XX243')

    def test_mobile_prepaid_does_not_mix_postpaid_billers(self):
        BbpsBillerMaster.objects.create(
            biller_id='BSNLPRE0001',
            biller_name='BSNL',
            biller_category='Mobile Prepaid',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        BbpsBillerMaster.objects.create(
            biller_id='AIRTELPST01',
            biller_name='Airtel Postpaid',
            biller_category='Mobile Postpaid',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        BbpsBillerMaster.objects.create(
            biller_id='MOBILEONLY01',
            biller_name='Generic Mobile',
            biller_category='Mobile',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        prepaid = get_billers_by_category('mobile-prepaid')
        prepaid_ids = {r['biller_id'] for r in prepaid}
        self.assertEqual(prepaid_ids, {'BSNLPRE0001'})
        postpaid = get_billers_by_category('mobile-postpaid')
        postpaid_ids = {r['biller_id'] for r in postpaid}
        self.assertIn('AIRTELPST01', postpaid_ids)
        self.assertIn('MOBILEONLY01', postpaid_ids)
        self.assertNotIn('BSNLPRE0001', postpaid_ids)

    def test_get_bill_categories_uses_partner_slug_for_mobile_cluster(self):
        BbpsBillerMaster.objects.create(
            biller_id='OTME00000XX244',
            biller_name='OTME',
            biller_category='Mobile',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        cats = get_bill_categories()
        self.assertEqual(
            [c for c in cats if c['id'] == 'mobile-postpaid'],
            [{'id': 'mobile-postpaid', 'name': 'Mobile Postpaid'}],
        )
