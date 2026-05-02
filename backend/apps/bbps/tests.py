from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.authentication.models import User
from apps.bbps.models import (
    BbpsBillerCcf1Config,
    BbpsBillerMaster,
    BbpsCategoryCommissionRule,
    BbpsFetchSession,
    BbpsPaymentAttempt,
    BbpsProviderBillerMap,
    BbpsServiceCategory,
    BbpsServiceProvider,
)
from apps.bbps.services import get_bill_categories, get_providers_by_category, governance_readiness_for_biller
from apps.bbps.service_flow.compliance import (
    compute_ccf1_if_required,
    enforce_cash_pan_rule,
    enforce_fetch_pay_linkage,
    enforce_plan_mdm_requirement,
)
from apps.bbps.service_flow.commission_service import resolve_commission_for_payment
from apps.core.exceptions import TransactionFailed


class MdmBillerParseTests(SimpleTestCase):
    """MDM response shape variants (camelCase / PascalCase / XML-style single root)."""

    def test_iter_billers_camel_list(self):
        from apps.bbps.service_flow.biller_sync import _iter_billers

        p = {'biller': [{'billerId': 'A', 'billerName': 'One'}]}
        self.assertEqual(len(_iter_billers(p)), 1)

    def test_iter_billers_pascal_wrapped(self):
        from apps.bbps.service_flow.biller_sync import _iter_billers

        p = {'BillerInfoResponse': {'Biller': [{'billerId': 'B', 'billerName': 'Two'}]}}
        self.assertEqual(len(_iter_billers(p)), 1)

    def test_iter_billers_nested_mdm_response(self):
        from apps.bbps.service_flow.biller_sync import _iter_billers

        p = {'extMdmResponse': {'biller': [{'billerId': 'C'}]}}
        self.assertEqual(len(_iter_billers(p)), 1)

    def test_iter_billers_deep_scan_fallback(self):
        from apps.bbps.service_flow.biller_sync import _iter_billers

        p = {'outer': {'middle': {'items': [{'billerId': 'Z9', 'billerName': 'Deep'}]}}}
        self.assertEqual(len(_iter_billers(p)), 1)

    def test_extract_response_code_pascal_nested(self):
        from apps.integrations.billavenue.parsers import extract_response_code

        p = {'SomeRoot': {'ResponseCode': '000'}}
        self.assertEqual(extract_response_code(p), '000')


class BbpsAttemptModelTests(TestCase):
    def test_idempotency_key_unique_constraint(self):
        user = User.objects.create_user(
            phone='9999999999',
            email='bbps-test@example.com',
            password='testpass123',
        )
        BbpsPaymentAttempt.objects.create(
            user=user,
            idempotency_key='dup-key',
            service_id='SVC1',
            amount_paise=100,
        )
        with self.assertRaises(Exception):
            BbpsPaymentAttempt.objects.create(
                user=user,
                idempotency_key='dup-key',
                service_id='SVC2',
                amount_paise=200,
            )


class BbpsGovernanceFlowTests(TestCase):
    def test_provider_discovery_from_mapping(self):
        cat = BbpsServiceCategory.objects.create(code='credit-card', name='Credit Card')
        prov = BbpsServiceProvider.objects.create(category=cat, code='hdfc-bank', name='HDFC', provider_type='bank')
        biller = BbpsBillerMaster.objects.create(
            biller_id='CC1001',
            biller_name='HDFC Credit Card',
            biller_category='credit-card',
            biller_status='ACTIVE',
        )
        BbpsProviderBillerMap.objects.create(provider=prov, biller_master=biller, is_active=True)

        providers = get_providers_by_category('credit-card')
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0]['provider_code'], 'hdfc-bank')
        self.assertEqual(providers[0]['biller_options'][0]['biller_id'], 'CC1001')

    def test_commission_resolution_shadow_ready(self):
        cat = BbpsServiceCategory.objects.create(code='credit-card', name='Credit Card')
        BbpsCategoryCommissionRule.objects.create(
            category=cat,
            rule_code='RULE1',
            commission_type='percentage',
            value=Decimal('2.5'),
            min_commission=Decimal('0'),
            max_commission=Decimal('0'),
            is_active=True,
        )
        out = resolve_commission_for_payment(
            amount=Decimal('100'),
            bill_data={'bill_type': 'credit-card', 'biller_id': 'CC1001'},
        )
        self.assertEqual(out['commission_rule_code'], 'RULE1')
        self.assertEqual(str(out['charge']), '2.5000')

    def test_fetch_pay_linkage_for_mandatory_fetch(self):
        user = User.objects.create_user(phone='9000000001', email='u1@example.com', password='testpass123')
        biller = BbpsBillerMaster.objects.create(
            biller_id='CC3001',
            biller_name='Fetch Biller',
            biller_category='credit-card',
            biller_status='ACTIVE',
            biller_fetch_requirement='MANDATORY',
        )
        with self.assertRaises(TransactionFailed):
            enforce_fetch_pay_linkage(
                user=user,
                biller=biller,
                input_params=[{'paramName': 'a', 'paramValue': '1'}],
                request_id='REQ1',
            )
        BbpsFetchSession.objects.create(
            user=user,
            biller_master=biller,
            request_id='REQ1',
            input_params={'input': [{'paramName': 'a', 'paramValue': '1'}]},
            biller_response={},
            amount_paise=100,
            raw_response={},
            status='FETCHED',
        )
        out = enforce_fetch_pay_linkage(
            user=user,
            biller=biller,
            input_params=[{'paramName': 'a', 'paramValue': '1'}],
            request_id='REQ1',
        )
        self.assertIsNotNone(out)

    def test_ccf1_computation_floor(self):
        biller = BbpsBillerMaster.objects.create(
            biller_id='CC4001',
            biller_name='CCF1 Biller',
            biller_category='ncmc-recharge',
            biller_status='ACTIVE',
        )
        BbpsBillerCcf1Config.objects.create(
            biller=biller,
            fee_code='CCF1',
            percent_fee=Decimal('1.2'),
            flat_fee=Decimal('100'),
            fee_min_amount=Decimal('1'),
            fee_max_amount=Decimal('2147483647'),
        )
        ccf = compute_ccf1_if_required(biller=biller, amount_paise=10000)
        self.assertIsNotNone(ccf)
        self.assertEqual(ccf.ccf1_paise, 259)

    def test_plan_mdm_mandatory_requires_active_plan_id(self):
        from apps.bbps.models import BbpsBillerPlanMeta

        biller = BbpsBillerMaster.objects.create(
            biller_id='CC5001',
            biller_name='Plan Biller',
            biller_category='mobile-prepaid',
            biller_status='ACTIVE',
            plan_mdm_requirement='MANDATORY',
        )
        with self.assertRaises(TransactionFailed):
            enforce_plan_mdm_requirement(biller=biller, plan_id='')
        BbpsBillerPlanMeta.objects.create(
            biller=biller,
            plan_id='PLAN-A',
            status='ACTIVE',
            amount_in_rupees=Decimal('10'),
        )
        enforce_plan_mdm_requirement(biller=biller, plan_id='PLAN-A')


class ApprovalFirstGovernanceTests(TestCase):
    def setUp(self):
        self.category = BbpsServiceCategory.objects.create(code='credit-card', name='Credit Card', is_active=True)
        self.provider = BbpsServiceProvider.objects.create(
            category=self.category,
            code='hdfc-cc',
            name='HDFC Credit Card',
            provider_type='bank',
            is_active=True,
        )
        self.biller = BbpsBillerMaster.objects.create(
            biller_id='OTME00005XXZ43',
            biller_name='HDFC Cards',
            biller_category='credit-card',
            biller_status='ACTIVE',
        )
        self.map = BbpsProviderBillerMap.objects.create(provider=self.provider, biller_master=self.biller, is_active=True)

    def test_provider_listing_requires_active_commission_rule(self):
        providers = get_providers_by_category('credit-card')
        self.assertEqual(providers, [])
        BbpsCategoryCommissionRule.objects.create(
            category=self.category,
            rule_code='DEFAULT-CREDIT-CARD',
            commission_type='flat',
            value=Decimal('5'),
            is_active=True,
        )
        providers = get_providers_by_category('credit-card')
        self.assertEqual(len(providers), 1)

    def test_biller_status_fluctuating_is_allowed(self):
        BbpsCategoryCommissionRule.objects.create(
            category=self.category,
            rule_code='RULE-1',
            commission_type='flat',
            value=Decimal('1'),
            is_active=True,
        )
        self.biller.biller_status = 'FLUCTUATING'
        self.biller.save(update_fields=['biller_status', 'updated_at'])
        providers = get_providers_by_category('credit-card')
        self.assertEqual(len(providers), 1)

    def test_governance_readiness_reports_no_rule_blocker(self):
        readiness = governance_readiness_for_biller(self.biller.biller_id)
        self.assertFalse(readiness['allowed'])
        self.assertIn('no_rule', readiness['blocked_by'])

    def test_sync_upsert_creates_pending_inactive_mapping(self):
        from apps.bbps.service_flow.biller_sync import _upsert_governance_rows

        row = {
            'billerCategory': 'credit-card',
            'billerName': 'HDFC Credit Card',
        }
        self.provider.delete()
        self.map.delete()
        result = _upsert_governance_rows(row, self.biller)
        self.assertTrue(result['provider_created'])
        created_provider = BbpsServiceProvider.objects.get(category=self.category)
        created_map = BbpsProviderBillerMap.objects.get(provider=created_provider, biller_master=self.biller)
        self.assertFalse(created_provider.is_active)
        self.assertFalse(created_map.is_active)
        self.assertEqual(created_provider.metadata.get('approval_status'), 'pending')
        self.assertEqual(created_map.metadata.get('approval_status'), 'pending')


class MdmCatalogPublishApiTests(TestCase):
    def test_mdm_catalog_publish_and_unpublish(self):
        from rest_framework.test import APIClient

        admin = User.objects.create_user(
            phone='9222222222',
            email='mdm-pub@test.com',
            password='secret123',
            role='Admin',
        )
        cat = BbpsServiceCategory.objects.create(code='mobile-recharge', name='Mobile', is_active=False)
        prov = BbpsServiceProvider.objects.create(
            category=cat,
            code='op-a',
            name='Operator A',
            is_active=False,
            metadata={'auto_synced': True},
        )
        biller = BbpsBillerMaster.objects.create(
            biller_id='B99001',
            biller_name='Test Telco',
            biller_category='Mobile',
            biller_status='ACTIVE',
        )
        m = BbpsProviderBillerMap.objects.create(
            provider=prov,
            biller_master=biller,
            is_active=False,
            metadata={'auto_synced': True},
        )
        client = APIClient()
        client.force_authenticate(user=admin)
        r = client.post('/api/bbps/admin/mdm-catalog/publish/', {'map_id': m.id, 'published': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body['success'])
        self.assertTrue(body['data'].get('commission_rule_created'))
        self.assertEqual(body['data'].get('warnings'), [])
        cat.refresh_from_db()
        prov.refresh_from_db()
        m.refresh_from_db()
        self.assertTrue(cat.is_active)
        self.assertTrue(prov.is_active)
        self.assertTrue(m.is_active)
        self.assertTrue(
            BbpsCategoryCommissionRule.objects.filter(
                category=cat,
                rule_code='mdm-catalog-default',
                is_deleted=False,
                is_active=True,
            ).exists()
        )
        cats = get_bill_categories()
        self.assertTrue(any(c['id'] == 'mobile-recharge' for c in cats))

        r2 = client.post('/api/bbps/admin/mdm-catalog/publish/', {'map_id': m.id, 'published': False}, format='json')
        self.assertEqual(r2.status_code, 200)
        m.refresh_from_db()
        self.assertFalse(m.is_active)

    def test_mdm_catalog_summary_and_bulk_publish(self):
        from rest_framework.test import APIClient

        admin = User.objects.create_user(
            phone='9333333333',
            email='mdm-summary@test.com',
            password='secret123',
            role='Admin',
        )
        cat = BbpsServiceCategory.objects.create(code='dth', name='DTH', is_active=False)
        prov = BbpsServiceProvider.objects.create(
            category=cat,
            code='dth-op',
            name='DTH OP',
            is_active=False,
            metadata={'auto_synced': True},
        )
        biller = BbpsBillerMaster.objects.create(
            biller_id='B99111',
            biller_name='DTH TEST',
            biller_category='DTH',
            biller_status='ACTIVE',
        )
        m = BbpsProviderBillerMap.objects.create(
            provider=prov,
            biller_master=biller,
            is_active=False,
            metadata={'auto_synced': True},
        )
        client = APIClient()
        client.force_authenticate(user=admin)
        s = client.get('/api/bbps/admin/mdm-catalog/summary/')
        self.assertEqual(s.status_code, 200)
        self.assertTrue(s.json()['success'])
        b = client.post(
            '/api/bbps/admin/mdm-catalog/bulk-publish/',
            {'map_ids': [m.id], 'published': True},
            format='json',
        )
        self.assertEqual(b.status_code, 200, b.content)
        m.refresh_from_db()
        self.assertTrue(m.is_active)


class ComplianceRulesTests(TestCase):
    def test_cash_pan_required_for_high_value(self):
        with self.assertRaises(TransactionFailed):
            enforce_cash_pan_rule(
                amount_paise=5000000,
                payment_mode='Cash',
                customer_info={'customerPan': '', 'customerName': ''},
            )
        enforce_cash_pan_rule(
            amount_paise=5000000,
            payment_mode='Cash',
            customer_info={'customerPan': 'ABCDE1234F', 'customerName': 'Tarun I'},
        )
