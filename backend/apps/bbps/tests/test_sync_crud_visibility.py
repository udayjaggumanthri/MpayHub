from django.test import TestCase

from apps.bbps.models import BbpsBillerMaster, BbpsProviderBillerMap, BbpsServiceCategory, BbpsServiceProvider
from apps.bbps.serializers import BillerSyncRequestSerializer
from apps.bbps.services import get_billers_by_category


class BbpsSyncCrudVisibilityTests(TestCase):
    def test_sync_request_rejects_more_than_2000_ids(self):
        data = {'biller_ids': [f'B{i}' for i in range(2001)]}
        ser = BillerSyncRequestSerializer(data=data)
        self.assertFalse(ser.is_valid())
        self.assertIn('biller_ids', ser.errors)

    def test_sync_request_deduplicates_ids(self):
        ser = BillerSyncRequestSerializer(data={'biller_ids': ['A1', 'A1', 'A2']})
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data['biller_ids'], ['A1', 'A2'])

    def test_user_listing_hides_local_inactive_and_soft_deleted(self):
        category = BbpsServiceCategory.objects.create(code='mobile-recharge', name='Mobile', is_active=True)
        provider = BbpsServiceProvider.objects.create(
            category=category,
            code='provider-mobile',
            name='Provider Mobile',
            is_active=True,
            provider_type='operator',
        )
        active = BbpsBillerMaster.objects.create(
            biller_id='B100',
            biller_name='Visible Biller',
            biller_category='mobile-recharge',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        inactive = BbpsBillerMaster.objects.create(
            biller_id='B101',
            biller_name='Hidden Biller',
            biller_category='mobile-recharge',
            biller_status='ACTIVE',
            is_active_local=False,
        )
        soft_deleted = BbpsBillerMaster.objects.create(
            biller_id='B102',
            biller_name='Deleted Biller',
            biller_category='mobile-recharge',
            biller_status='ACTIVE',
            is_active_local=True,
            soft_deleted_at=active.created_at,
        )
        BbpsProviderBillerMap.objects.create(provider=provider, biller_master=active, is_active=True)
        BbpsProviderBillerMap.objects.create(provider=provider, biller_master=inactive, is_active=True)
        BbpsProviderBillerMap.objects.create(provider=provider, biller_master=soft_deleted, is_active=True)

        out = get_billers_by_category('mobile-recharge')
        returned_ids = {row['biller_id'] for row in out}
        self.assertIn('B100', returned_ids)
        self.assertNotIn('B101', returned_ids)
        self.assertNotIn('B102', returned_ids)
