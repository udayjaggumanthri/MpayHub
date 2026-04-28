from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.authentication.models import User
from apps.bbps.models import (
    BbpsBillerCcf1Config,
    BbpsBillerMaster,
    BbpsBillerPaymentChannelLimit,
    BbpsBillerPaymentModeLimit,
    BbpsCategoryCommissionRule,
    BbpsFetchSession,
    BbpsPaymentAttempt,
    BbpsProviderBillerMap,
    BbpsServiceCategory,
    BbpsServiceProvider,
)
from apps.bbps.services import get_providers_by_category
from apps.bbps.service_flow.compliance import (
    compute_ccf1_if_required,
    enforce_biller_mode_channel_constraints,
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

    def test_mode_channel_matrix_validation(self):
        biller = BbpsBillerMaster.objects.create(
            biller_id='CC2001',
            biller_name='Test Biller',
            biller_category='credit-card',
            biller_status='ACTIVE',
        )
        BbpsBillerPaymentChannelLimit.objects.create(biller=biller, payment_channel='AGT', min_amount=0, max_amount=0)
        BbpsBillerPaymentModeLimit.objects.create(biller=biller, payment_mode='UPI', min_amount=0, max_amount=0)
        enforce_biller_mode_channel_constraints(
            biller=biller,
            payment_mode='UPI',
            payment_channel='AGT',
            amount=Decimal('10'),
        )
        with self.assertRaises(TransactionFailed):
            enforce_biller_mode_channel_constraints(
                biller=biller,
                payment_mode='Credit Card',
                payment_channel='AGT',
                amount=Decimal('10'),
            )

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
