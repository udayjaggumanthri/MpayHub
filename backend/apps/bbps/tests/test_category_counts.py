"""Tests for the biller-master category-counts admin endpoint."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.bbps.models import BbpsBillerMaster
from apps.integrations.billavenue.registry import activate_billavenue_config, get_or_create_billavenue_mode_row


class CategoryCountsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9111888001',
            email='cat.admin@example.com',
            password='TestPass123!',
            role='Admin',
            user_id='CATADM1',
        )
        cfg = get_or_create_billavenue_mode_row('prod')
        cfg.enabled = True
        cfg.save()
        activate_billavenue_config(cfg)
        for i in range(3):
            BbpsBillerMaster.objects.create(
                environment='prod',
                biller_id=f'MOBI0000000{i}',
                biller_name=f'Mobile Biller {i}',
                biller_category='Mobile Postpaid',
                biller_status='ACTIVE',
                is_active_local=(i != 2),
            )
        BbpsBillerMaster.objects.create(
            environment='prod',
            biller_id='ELEC00000001',
            biller_name='Electric Co',
            biller_category='Electricity',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        BbpsBillerMaster.objects.create(
            environment='uat',
            biller_id='UATB00000001',
            biller_name='UAT Biller',
            biller_category='DTH',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_counts_for_prod(self):
        res = self.client.get('/api/bbps/admin/biller-master/category-counts/', {'environment': 'prod'})
        self.assertEqual(res.status_code, 200, res.content)
        data = res.data['data']
        self.assertEqual(data['catalog_environment'], 'prod')
        cats = {c['category']: c for c in data['categories']}
        self.assertEqual(cats['Mobile Postpaid']['total'], 3)
        self.assertEqual(cats['Mobile Postpaid']['visible'], 2)
        self.assertEqual(cats['Mobile Postpaid']['hidden'], 1)
        self.assertEqual(cats['Electricity']['total'], 1)
        self.assertNotIn('DTH', cats)
        self.assertEqual(data['totals']['total'], 4)

    def test_counts_for_uat(self):
        res = self.client.get('/api/bbps/admin/biller-master/category-counts/', {'environment': 'uat'})
        self.assertEqual(res.status_code, 200)
        cats = {c['category']: c for c in res.data['data']['categories']}
        self.assertIn('DTH', cats)
        self.assertNotIn('Electricity', cats)

    def test_retailer_forbidden(self):
        retailer = User.objects.create_user(
            phone='9111888002',
            email='cat.ret@example.com',
            password='TestPass123!',
            role='Retailer',
            user_id='CATRET1',
        )
        c = APIClient()
        c.force_authenticate(user=retailer)
        self.assertEqual(c.get('/api/bbps/admin/biller-master/category-counts/').status_code, 403)
