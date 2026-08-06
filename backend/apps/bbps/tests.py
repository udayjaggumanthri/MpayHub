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
from apps.bbps.services import get_bill_categories, get_billers_by_category, get_providers_by_category, governance_readiness_for_biller
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

    def test_fetch_pay_linkage_selects_session_matching_request_id(self):
        user = User.objects.create_user(phone='9000000002', email='u2@example.com', password='testpass123')
        biller = BbpsBillerMaster.objects.create(
            biller_id='CC3002',
            biller_name='Multi Fetch',
            biller_category='credit-card',
            biller_status='ACTIVE',
            biller_fetch_requirement='MANDATORY',
        )
        inp = [{'paramName': 'a', 'paramValue': '1'}]
        stored = {'input': inp}
        BbpsFetchSession.objects.create(
            user=user,
            biller_master=biller,
            request_id='REQ_OLD',
            input_params=stored,
            biller_response={},
            amount_paise=100,
            raw_response={},
            status='FETCHED',
        )
        BbpsFetchSession.objects.create(
            user=user,
            biller_master=biller,
            request_id='REQ_NEW',
            input_params=stored,
            biller_response={},
            amount_paise=200,
            raw_response={},
            status='FETCHED',
        )
        session = enforce_fetch_pay_linkage(
            user=user,
            biller=biller,
            input_params=inp,
            request_id='REQ_OLD',
        )
        self.assertEqual(session.request_id, 'REQ_OLD')

    def test_fetch_pay_linkage_input_params_order_insensitive(self):
        user = User.objects.create_user(phone='9000000005', email='u5@example.com', password='testpass123')
        biller = BbpsBillerMaster.objects.create(
            biller_id='CC3005',
            biller_name='Order Test',
            biller_category='credit-card',
            biller_status='ACTIVE',
            biller_fetch_requirement='MANDATORY',
        )
        stored = {
            'input': [
                {'paramName': 'a', 'paramValue': '1'},
                {'paramName': 'a b', 'paramValue': '2'},
            ]
        }
        BbpsFetchSession.objects.create(
            user=user,
            biller_master=biller,
            request_id='REQ_ORDER',
            input_params=stored,
            biller_response={},
            amount_paise=100,
            raw_response={},
            status='FETCHED',
        )
        pay_params = [
            {'paramName': 'a b', 'paramValue': '2'},
            {'paramName': 'a', 'paramValue': '1'},
        ]
        session = enforce_fetch_pay_linkage(
            user=user,
            biller=biller,
            input_params=pay_params,
            request_id='REQ_ORDER',
        )
        self.assertEqual(session.request_id, 'REQ_ORDER')

    def test_fetch_pay_linkage_placeholder_param_names_must_match_mdm_exactly(self):
        """BillAvenue expects ``paramName`` exactly as in MDM (e.g. ``a b``, not ``ab``)."""
        user = User.objects.create_user(phone='9000000006', email='u6@example.com', password='testpass123')
        biller = BbpsBillerMaster.objects.create(
            biller_id='CC3006',
            biller_name='Wire exact',
            biller_category='credit-card',
            biller_status='ACTIVE',
            biller_fetch_requirement='MANDATORY',
        )
        BbpsFetchSession.objects.create(
            user=user,
            biller_master=biller,
            request_id='REQ_COMP',
            input_params={'input': [{'paramName': 'a b', 'paramValue': '2'}, {'paramName': 'a', 'paramValue': '1'}]},
            biller_response={},
            amount_paise=100,
            raw_response={},
            status='FETCHED',
        )
        with self.assertRaises(TransactionFailed):
            enforce_fetch_pay_linkage(
                user=user,
                biller=biller,
                input_params=[{'paramName': 'ab', 'paramValue': '2'}, {'paramName': 'a', 'paramValue': '1'}],
                request_id='REQ_COMP',
            )
        session = enforce_fetch_pay_linkage(
            user=user,
            biller=biller,
            input_params=[{'paramName': 'a b', 'paramValue': '2'}, {'paramName': 'a', 'paramValue': '1'}],
            request_id='REQ_COMP',
        )
        self.assertEqual(session.request_id, 'REQ_COMP')

    def test_fetch_pay_linkage_unknown_request_id_raises(self):
        user = User.objects.create_user(phone='9000000003', email='u3@example.com', password='testpass123')
        biller = BbpsBillerMaster.objects.create(
            biller_id='CC3003',
            biller_name='No Match',
            biller_category='credit-card',
            biller_status='ACTIVE',
            biller_fetch_requirement='MANDATORY',
        )
        BbpsFetchSession.objects.create(
            user=user,
            biller_master=biller,
            request_id='REQ_A',
            input_params={'input': [{'paramName': 'a', 'paramValue': '1'}]},
            biller_response={},
            amount_paise=100,
            raw_response={},
            status='FETCHED',
        )
        with self.assertRaises(TransactionFailed):
            enforce_fetch_pay_linkage(
                user=user,
                biller=biller,
                input_params=[{'paramName': 'a', 'paramValue': '1'}],
                request_id='REQ_MISSING',
            )

    def test_fetch_pay_linkage_requires_request_id_when_multiple_open_fetches(self):
        user = User.objects.create_user(phone='9000000004', email='u4@example.com', password='testpass123')
        biller = BbpsBillerMaster.objects.create(
            biller_id='CC3004',
            biller_name='Two Open',
            biller_category='credit-card',
            biller_status='ACTIVE',
            biller_fetch_requirement='MANDATORY',
        )
        inp = {'input': [{'paramName': 'a', 'paramValue': '1'}]}
        BbpsFetchSession.objects.create(
            user=user,
            biller_master=biller,
            request_id='R1',
            input_params=inp,
            biller_response={},
            amount_paise=100,
            raw_response={},
            status='FETCHED',
        )
        BbpsFetchSession.objects.create(
            user=user,
            biller_master=biller,
            request_id='R2',
            input_params=inp,
            biller_response={},
            amount_paise=200,
            raw_response={},
            status='FETCHED',
        )
        with self.assertRaises(TransactionFailed):
            enforce_fetch_pay_linkage(
                user=user,
                biller=biller,
                input_params=[{'paramName': 'a', 'paramValue': '1'}],
                request_id='',
            )

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


class BbpsMobileCategoryRoutingTests(TestCase):
    """Regression: BillAvenue ``Mobile`` must map to partner route ``mobile-postpaid`` for list + APIs."""

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
        self.assertEqual([c for c in cats if c['id'] == 'mobile-postpaid'], [{'id': 'mobile-postpaid', 'name': 'Mobile Postpaid'}])


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
        self.assertTrue(any(c['id'] == 'mobile-postpaid' for c in cats))

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
