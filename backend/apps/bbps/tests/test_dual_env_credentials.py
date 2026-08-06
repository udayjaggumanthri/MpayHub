"""Tests for dual UAT/PROD BillAvenue credentials and env-scoped MDM catalog."""

from django.test import TestCase
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.bbps.catalog.env import active_bbps_environment, biller_master_qs_for_env, get_biller_master
from apps.bbps.catalog.persist_biller import mark_unseen_billers_stale, persist_biller_from_mdm_row
from apps.bbps.models import BbpsBillerMaster
from apps.bbps.services import get_bill_categories, get_billers_by_category
from apps.integrations.billavenue.registry import (
    activate_billavenue_config,
    get_active_billavenue_config,
    get_or_create_billavenue_mode_row,
)


def _admin_client():
    user = User.objects.create_user(
        phone='9199990001',
        email='bbps_admin_dual@example.com',
        password='pass12345',
        role='Admin',
        user_id='BBPSDUAL1',
        first_name='BBPS',
        last_name='Admin',
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


class DualEnvCredentialsTests(TestCase):
    def test_save_prod_does_not_alter_uat_secrets(self):
        uat = get_or_create_billavenue_mode_row('uat')
        uat.access_code = 'UAT-ACCESS'
        uat.set_working_key('uat-working-key-value')
        uat.set_iv('uat-iv-value-16b')
        uat.enabled = True
        uat.save()
        activate_billavenue_config(uat)

        prod = get_or_create_billavenue_mode_row('prod')
        prod.access_code = 'PROD-ACCESS'
        prod.set_working_key('prod-working-key-value')
        prod.set_iv('prod-iv-value-16b')
        prod.enabled = True
        prod.base_url = 'https://api.billavenue.com'
        prod.save()

        uat.refresh_from_db()
        self.assertEqual(uat.access_code, 'UAT-ACCESS')
        self.assertEqual(uat.get_working_key(), 'uat-working-key-value')
        self.assertEqual(uat.get_iv(), 'uat-iv-value-16b')
        self.assertNotEqual(prod.get_working_key(), uat.get_working_key())

    def test_make_active_switches_client_resolution(self):
        uat = get_or_create_billavenue_mode_row('uat')
        uat.enabled = True
        uat.base_url = 'https://stgapi.billavenue.com'
        uat.save()
        activate_billavenue_config(uat)
        self.assertEqual(get_active_billavenue_config().mode, 'uat')
        self.assertEqual(active_bbps_environment(), 'uat')

        prod = get_or_create_billavenue_mode_row('prod')
        prod.enabled = True
        prod.base_url = 'https://api.billavenue.com'
        prod.save()
        activate_billavenue_config(prod)
        self.assertEqual(get_active_billavenue_config().mode, 'prod')
        self.assertEqual(active_bbps_environment(), 'prod')
        uat.refresh_from_db()
        self.assertFalse(uat.is_active)

    def test_config_get_without_mode_returns_config(self):
        client, _ = _admin_client()
        uat = get_or_create_billavenue_mode_row('uat')
        uat.enabled = True
        uat.base_url = 'https://stgapi.billavenue.com'
        uat.save()
        activate_billavenue_config(uat)
        res = client.get('/api/bbps/admin/config/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get('success'))
        self.assertIsNotNone(res.data.get('data', {}).get('config'))
        self.assertIn('environments', res.data.get('data', {}))

    def test_secrets_scoped_by_mode(self):
        client, _ = _admin_client()
        uat = get_or_create_billavenue_mode_row('uat')
        uat.enabled = True
        uat.base_url = 'https://stgapi.billavenue.com'
        uat.set_working_key('keep-uat')
        uat.save()
        prod = get_or_create_billavenue_mode_row('prod')
        prod.enabled = True
        prod.base_url = 'https://api.billavenue.com'
        prod.save()

        res = client.post(
            '/api/bbps/admin/config/secrets/',
            {
                'mode': 'prod',
                'working_key': 'only-prod-key-32hexchars0001',
                'iv': '000102030405060708090a0b0c0d0e0f',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        uat.refresh_from_db()
        prod.refresh_from_db()
        self.assertEqual(uat.get_working_key(), 'keep-uat')
        self.assertEqual(prod.get_working_key(), 'only-prod-key-32hexchars0001')


class EnvScopedCatalogTests(TestCase):
    def setUp(self):
        self.uat = get_or_create_billavenue_mode_row('uat')
        self.uat.enabled = True
        self.uat.base_url = 'https://stgapi.billavenue.com'
        self.uat.save()
        activate_billavenue_config(self.uat)

        self.prod = get_or_create_billavenue_mode_row('prod')
        self.prod.enabled = True
        self.prod.base_url = 'https://api.billavenue.com'
        self.prod.save()

    def test_persist_isolates_environments(self):
        raw = {
            'billerId': 'AAST00000RAJ67',
            'billerName': 'UAT Biller',
            'billerCategory': 'Electricity',
            'billerStatus': 'ACTIVE',
        }
        persist_biller_from_mdm_row(raw, environment='uat')
        raw_prod = {**raw, 'billerName': 'PROD Biller'}
        persist_biller_from_mdm_row(raw_prod, environment='prod')

        uat_row = BbpsBillerMaster.objects.get(environment='uat', biller_id='AAST00000RAJ67', is_deleted=False)
        prod_row = BbpsBillerMaster.objects.get(environment='prod', biller_id='AAST00000RAJ67', is_deleted=False)
        self.assertEqual(uat_row.biller_name, 'UAT Biller')
        self.assertEqual(prod_row.biller_name, 'PROD Biller')

        activate_billavenue_config(self.prod)
        self.assertEqual(get_biller_master('AAST00000RAJ67').biller_name, 'PROD Biller')
        activate_billavenue_config(self.uat)
        self.assertEqual(get_biller_master('AAST00000RAJ67').biller_name, 'UAT Biller')

    def test_browse_filters_active_env(self):
        persist_biller_from_mdm_row(
            {
                'billerId': 'UATONLY01',
                'billerName': 'Only UAT',
                'billerCategory': 'Electricity',
                'billerStatus': 'ACTIVE',
            },
            environment='uat',
        )
        persist_biller_from_mdm_row(
            {
                'billerId': 'PRODONLY01',
                'billerName': 'Only PROD',
                'billerCategory': 'Electricity',
                'billerStatus': 'ACTIVE',
            },
            environment='prod',
        )
        activate_billavenue_config(self.prod)
        billers = get_billers_by_category('Electricity')
        ids = {b['biller_id'] for b in billers}
        self.assertIn('PRODONLY01', ids)
        self.assertNotIn('UATONLY01', ids)

        activate_billavenue_config(self.uat)
        billers = get_billers_by_category('Electricity')
        ids = {b['biller_id'] for b in billers}
        self.assertIn('UATONLY01', ids)
        self.assertNotIn('PRODONLY01', ids)
        cats = get_bill_categories()
        self.assertTrue(any(c.get('id') for c in cats))

    def test_clear_all_scoped_and_stale_scoped(self):
        persist_biller_from_mdm_row(
            {
                'billerId': 'KEEPPROD',
                'billerName': 'Keep',
                'billerCategory': 'Water',
                'billerStatus': 'ACTIVE',
            },
            environment='prod',
        )
        persist_biller_from_mdm_row(
            {
                'billerId': 'CLEARMIE',
                'billerName': 'Clear me',
                'billerCategory': 'Water',
                'billerStatus': 'ACTIVE',
            },
            environment='uat',
        )
        activate_billavenue_config(self.uat)
        client, _ = _admin_client()
        res = client.post('/api/bbps/admin/biller-master/clear-all/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(
            BbpsBillerMaster.objects.filter(environment='uat', biller_id='CLEARMIE', is_deleted=False).exists()
        )
        self.assertTrue(
            BbpsBillerMaster.objects.filter(environment='prod', biller_id='KEEPPROD', is_deleted=False).exists()
        )

        mark_unseen_billers_stale(['MISSING'], set(), environment='uat')
        # Should not mark PROD rows stale
        prod = BbpsBillerMaster.objects.get(environment='prod', biller_id='KEEPPROD')
        self.assertFalse(prod.is_stale)

    def test_activate_endpoint_switches_live(self):
        client, _ = _admin_client()
        uat = get_or_create_billavenue_mode_row('uat')
        uat.access_code = 'UAT-ACCESS'
        uat.institute_id = 'PI39'
        uat.set_working_key('uat-working-key-value')
        uat.set_iv('uat-iv-value-16b')
        uat.enabled = True
        uat.base_url = 'https://stgapi.billavenue.com'
        uat.save()
        prod = get_or_create_billavenue_mode_row('prod')
        prod.enabled = True
        prod.base_url = 'https://api.billavenue.com'
        prod.save()
        activate_billavenue_config(prod)
        res = client.post('/api/bbps/admin/config/activate/', {'mode': 'uat'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['data']['live_mode'], 'uat')
        self.assertEqual(active_bbps_environment(), 'uat')
        self.assertTrue(get_active_billavenue_config().enabled)
        prod.refresh_from_db()
        self.assertFalse(prod.is_active)

    def test_admin_list_filters_by_environment_param(self):
        client, _ = _admin_client()
        persist_biller_from_mdm_row(
            {'billerId': 'LISTUAT1', 'billerName': 'U', 'billerCategory': 'X', 'billerStatus': 'ACTIVE'},
            environment='uat',
        )
        persist_biller_from_mdm_row(
            {'billerId': 'LISTPROD1', 'billerName': 'P', 'billerCategory': 'X', 'billerStatus': 'ACTIVE'},
            environment='prod',
        )
        activate_billavenue_config(self.prod)
        res = client.get('/api/bbps/admin/biller-master/', {'environment': 'uat'})
        self.assertEqual(res.status_code, 200)
        ids = {b['biller_id'] for b in res.data['data']['billers']}
        self.assertIn('LISTUAT1', ids)
        self.assertNotIn('LISTPROD1', ids)
        self.assertEqual(res.data['data']['catalog_environment'], 'uat')
        self.assertEqual(res.data['data']['live_mode'], 'prod')
        self.assertIn('catalog_counts', res.data['data'])

    def test_delete_and_bulk_delete_remove_from_directory(self):
        client, _ = _admin_client()
        persist_biller_from_mdm_row(
            {'billerId': 'DELONE1', 'billerName': 'One', 'billerCategory': 'X', 'billerStatus': 'ACTIVE'},
            environment='prod',
        )
        persist_biller_from_mdm_row(
            {'billerId': 'DELBULK1', 'billerName': 'Bulk1', 'billerCategory': 'X', 'billerStatus': 'ACTIVE'},
            environment='prod',
        )
        persist_biller_from_mdm_row(
            {'billerId': 'DELBULK2', 'billerName': 'Bulk2', 'billerCategory': 'X', 'billerStatus': 'ACTIVE'},
            environment='prod',
        )
        persist_biller_from_mdm_row(
            {'billerId': 'KEEPUAT1', 'billerName': 'Keep', 'billerCategory': 'X', 'billerStatus': 'ACTIVE'},
            environment='uat',
        )
        activate_billavenue_config(self.prod)
        one = BbpsBillerMaster.objects.get(environment='prod', biller_id='DELONE1', is_deleted=False)
        res = client.delete(f'/api/bbps/admin/biller-master/{one.pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(
            BbpsBillerMaster.objects.filter(environment='prod', biller_id='DELONE1', is_deleted=False).exists()
        )
        listed = client.get('/api/bbps/admin/biller-master/', {'environment': 'prod'})
        ids = {b['biller_id'] for b in listed.data['data']['billers']}
        self.assertNotIn('DELONE1', ids)

        bulk = client.post(
            '/api/bbps/admin/biller-master/bulk-delete/',
            {'environment': 'prod', 'biller_ids': ['DELBULK1', 'DELBULK2']},
            format='json',
        )
        self.assertEqual(bulk.status_code, 200)
        self.assertEqual(bulk.data['data']['deleted_count'], 2)
        self.assertTrue(
            BbpsBillerMaster.objects.filter(environment='uat', biller_id='KEEPUAT1', is_deleted=False).exists()
        )

    def test_activate_live_blocked_without_secrets(self):
        client, _ = _admin_client()
        uat = get_or_create_billavenue_mode_row('uat')
        uat.access_code = 'UAT-ACCESS'
        uat.institute_id = 'PI39'
        uat.enabled = True
        uat.base_url = 'https://stgapi.billavenue.com'
        uat.save()
        activate_billavenue_config(uat)

        res = client.post('/api/bbps/admin/config/activate/', {'mode': 'uat'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('Working Key', res.data['message'])
        self.assertIn('working_key', res.data['data']['missing_fields'])
        self.assertIn('iv', res.data['data']['missing_fields'])

    def test_secrets_reject_literal_iv_label(self):
        client, _ = _admin_client()
        uat = get_or_create_billavenue_mode_row('uat')
        res = client.post(
            '/api/bbps/admin/config/secrets/',
            {'mode': 'uat', 'config_id': uat.pk, 'iv': 'IV'},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        blob = str(res.data.get('message') or '') + str(res.data.get('errors') or '')
        self.assertIn('IV', blob)
