"""Tests for BBPS provider float (company BillAvenue balance tracking)."""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.bbps.models import BbpsProviderFloatLedger
from apps.bbps.service_flow.provider_float import (
    BbpsProviderFloatInsufficient,
    assert_float_available,
    credit_float_for_refund,
    debit_float_for_payment,
    get_float_status,
    set_float_balance,
    update_float_settings,
)
from apps.integrations.billavenue.registry import activate_billavenue_config, get_or_create_billavenue_mode_row


def _user(*, phone, email, role, user_id, **extra):
    return User.objects.create_user(
        phone=phone,
        email=email,
        password='TestPass123!',
        role=role,
        user_id=user_id,
        first_name=extra.get('first_name', 'Test'),
        last_name=extra.get('last_name', 'User'),
    )


class ProviderFloatServiceTests(TestCase):
    def setUp(self):
        self.admin = _user(
            phone='9111000001',
            email='float.admin@example.com',
            role='Admin',
            user_id='FLOATADM1',
            first_name='Float',
            last_name='Admin',
        )
        cfg = get_or_create_billavenue_mode_row('prod')
        cfg.enabled = True
        cfg.save()
        activate_billavenue_config(cfg)

    def test_set_override_writes_ledger(self):
        out = set_float_balance(
            admin_user=self.admin,
            new_balance=Decimal('1000000.0000'),
            remarks='Morning BA dashboard top-up 10L',
            environment='prod',
        )
        self.assertEqual(out['balance'], '1000000.0000')
        self.assertEqual(BbpsProviderFloatLedger.objects.filter(entry_type='MANUAL_SET').count(), 1)
        entry = BbpsProviderFloatLedger.objects.get(entry_type='MANUAL_SET')
        self.assertEqual(entry.balance_after, Decimal('1000000.0000'))
        self.assertEqual(entry.balance_before, Decimal('0.0000'))

        out2 = set_float_balance(
            admin_user=self.admin,
            new_balance=Decimal('700000.0000'),
            remarks='Evening override after recharge to 7L',
            environment='prod',
        )
        self.assertEqual(out2['balance'], '700000.0000')
        self.assertEqual(BbpsProviderFloatLedger.objects.filter(entry_type='MANUAL_SET').count(), 2)

    def test_assert_blocks_when_insufficient(self):
        set_float_balance(
            admin_user=self.admin,
            new_balance=Decimal('100.0000'),
            remarks='Seed small float for gate test',
            environment='prod',
        )
        with self.assertRaises(BbpsProviderFloatInsufficient) as ctx:
            assert_float_available(Decimal('500.0000'), environment='prod')
        self.assertIn('temporarily unavailable', str(ctx.exception).lower())

    def test_assert_blocks_when_balance_not_initialized(self):
        with self.assertRaises(BbpsProviderFloatInsufficient):
            assert_float_available(Decimal('1.0000'), environment='prod')

    def test_assert_blocks_when_balance_hits_threshold(self):
        set_float_balance(
            admin_user=self.admin,
            new_balance=Decimal('8000.0000'),
            remarks='Seed float for threshold gate test',
            environment='prod',
        )
        update_float_settings(
            admin_user=self.admin,
            low_balance_threshold=Decimal('8000.0000'),
            enforcement_enabled=True,
            environment='prod',
        )
        with self.assertRaises(BbpsProviderFloatInsufficient):
            assert_float_available(Decimal('100.0000'), environment='prod')

    def test_enforcement_off_bypasses_gate(self):
        set_float_balance(
            admin_user=self.admin,
            new_balance=Decimal('10.0000'),
            remarks='Seed tiny float',
            environment='prod',
        )
        update_float_settings(admin_user=self.admin, enforcement_enabled=False, environment='prod')
        assert_float_available(Decimal('99999.0000'), environment='prod')  # must not raise

    def test_debit_and_idempotent_double_debit(self):
        set_float_balance(
            admin_user=self.admin,
            new_balance=Decimal('1000.0000'),
            remarks='Seed for debit test',
            environment='prod',
        )
        e1 = debit_float_for_payment('SVCFLOAT1', Decimal('250.0000'), remarks='pay1')
        self.assertIsNotNone(e1)
        status = get_float_status('prod')
        self.assertEqual(status['balance'], '750.0000')

        e2 = debit_float_for_payment('SVCFLOAT1', Decimal('250.0000'), remarks='pay1-retry')
        self.assertEqual(e1.pk, e2.pk)
        self.assertEqual(get_float_status('prod')['balance'], '750.0000')
        self.assertEqual(
            BbpsProviderFloatLedger.objects.filter(entry_type='AUTO_DEBIT', service_id='SVCFLOAT1').count(),
            1,
        )

    def test_refund_credit(self):
        set_float_balance(
            admin_user=self.admin,
            new_balance=Decimal('1000.0000'),
            remarks='Seed for refund test',
            environment='prod',
        )
        debit_float_for_payment('SVCREF1', Decimal('300.0000'))
        credit_float_for_refund('SVCREF1', Decimal('300.0000'))
        self.assertEqual(get_float_status('prod')['balance'], '1000.0000')
        credit_float_for_refund('SVCREF1', Decimal('300.0000'))  # idempotent
        self.assertEqual(get_float_status('prod')['balance'], '1000.0000')


class ProviderFloatAPITests(TestCase):
    def setUp(self):
        self.admin = _user(
            phone='9111000011',
            email='float.api.admin@example.com',
            role='Admin',
            user_id='FLOATAPI1',
        )
        self.retailer = _user(
            phone='9111000012',
            email='float.api.ret@example.com',
            role='Retailer',
            user_id='FLOATAPI2',
        )
        cfg = get_or_create_billavenue_mode_row('prod')
        cfg.enabled = True
        cfg.save()
        activate_billavenue_config(cfg)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin)
        self.ret_client = APIClient()
        self.ret_client.force_authenticate(user=self.retailer)

    def test_retailer_forbidden(self):
        res = self.ret_client.get('/api/bbps/admin/provider-float/')
        self.assertEqual(res.status_code, 403)

    def test_admin_set_and_get(self):
        res = self.admin_client.post(
            '/api/bbps/admin/provider-float/set/',
            {
                'environment': 'prod',
                'new_balance': '500000.00',
                'remarks': 'Synced from BillAvenue dashboard morning balance',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['data']['float']['balance'], '500000.0000')

        listed = self.admin_client.get('/api/bbps/admin/provider-float/', {'environment': 'prod'})
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data['data']['float']['balance'], '500000.0000')
        self.assertGreaterEqual(listed.data['data']['ledger']['pagination']['total'], 1)

    def test_settings_patch(self):
        self.admin_client.post(
            '/api/bbps/admin/provider-float/set/',
            {'environment': 'prod', 'new_balance': '1000', 'remarks': 'Seed settings test float'},
            format='json',
        )
        res = self.admin_client.patch(
            '/api/bbps/admin/provider-float/settings/',
            {
                'environment': 'prod',
                'low_balance_threshold': '100.00',
                'enforcement_enabled': False,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['data']['float']['enforcement_enabled'], False)
        self.assertEqual(res.data['data']['float']['low_balance_threshold'], '100.0000')


@override_settings(BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED=False)
class ProviderFloatPaymentGateTests(TestCase):
    def setUp(self):
        self.retailer = _user(
            phone='9111000022',
            email='float.pay.ret@example.com',
            role='Retailer',
            user_id='FLOATPAYR',
        )
        User.objects.filter(pk=self.retailer.pk).update(mpin_hash=None)
        self.retailer.refresh_from_db()
        self.client = APIClient()
        self.client.force_authenticate(user=self.retailer)

    @patch('apps.bbps.views.assert_module_available')
    @patch('apps.bbps.views.assert_can_pay_out')
    @patch('apps.bbps.views.process_bill_payment_flow')
    def test_pay_view_maps_float_insufficient(self, mock_flow, _mock_pay_out, _mock_module):
        mock_flow.side_effect = BbpsProviderFloatInsufficient()
        res = self.client.post(
            '/api/bbps/pay/',
            {
                'biller_id': 'TESTFLOAT001',
                'biller': 'Float Test',
                'bill_type': 'Insurance',
                'amount': '100.00',
                'payment_mode': 'Cash',
                'init_channel': 'AGT',
                'service_id': 'PMBBPSFLOATGATE1',
                'request_id': 'REQFLOATGATE1',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 503, res.content)
        body = res.json()
        self.assertFalse(body.get('success'))
        err = body.get('error') or {}
        self.assertEqual(err.get('code'), 'BBPS_PROVIDER_FLOAT_INSUFFICIENT')
        self.assertIn('temporarily unavailable', (body.get('message') or '').lower())
        mock_flow.assert_called()
