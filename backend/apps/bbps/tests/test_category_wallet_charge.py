"""Category wallet service charges and BillAvenue settings access."""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.bbps.models import BbpsBillerMaster, BbpsCategoryWalletCharge, BillPayment
from apps.bbps.service_flow.bbps_wallet_charge import resolve_bbps_wallet_service_charge
from apps.core.models import RoleModulePermission
from apps.core.module_permissions import seed_modules_and_permissions
from apps.integrations.billavenue.registry import activate_billavenue_config, get_or_create_billavenue_mode_row
from apps.wallets.models import Wallet


def _user(*, phone, email, role, user_id):
    return User.objects.create_user(
        phone=phone,
        email=email,
        password='TestPass123!',
        role=role,
        user_id=user_id,
        first_name='Charge',
        last_name='Tester',
    )


@override_settings(BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED=False, BBPS_SERVICE_CHARGE='5.00')
class CategoryWalletChargeTests(TestCase):
    def setUp(self):
        seed_modules_and_permissions()
        self.admin = _user(phone='9100001001', email='chg.admin@example.com', role='Admin', user_id='CHGADMIN1')
        self.super = _user(phone='9100001002', email='chg.super@example.com', role='Super Admin', user_id='CHGSUPER1')
        self.retailer = _user(phone='9100001003', email='chg.ret@example.com', role='Retailer', user_id='CHGRET001')
        cfg = get_or_create_billavenue_mode_row('prod')
        cfg.enabled = True
        cfg.bbps_wallet_service_charge_mode = 'FLAT'
        cfg.bbps_wallet_service_charge_flat = Decimal('5.0000')
        cfg.bbps_wallet_service_charge_percent = Decimal('0')
        cfg.save()
        activate_billavenue_config(cfg, user=self.super)
        self.cfg = cfg

    def test_missing_category_row_uses_global_charge(self):
        info = resolve_bbps_wallet_service_charge(amount=Decimal('1000'), category_code='electricity')
        self.assertEqual(info['charge'], Decimal('5.00'))
        self.assertEqual(info['source'], 'billavenue_config')
        self.assertEqual(info['category_code'], 'electricity')

    def test_electricity_percent_does_not_change_prepaid(self):
        BbpsCategoryWalletCharge.objects.create(
            category_code='electricity',
            mode='PERCENT',
            flat=Decimal('0'),
            percent=Decimal('10'),
            is_active=True,
        )
        electricity = resolve_bbps_wallet_service_charge(amount=Decimal('1000'), category_code='electricity')
        prepaid = resolve_bbps_wallet_service_charge(amount=Decimal('1000'), category_code='mobile-prepaid')
        self.assertEqual(electricity['charge'], Decimal('100.00'))
        self.assertEqual(electricity['source'], 'category')
        self.assertEqual(prepaid['charge'], Decimal('5.00'))
        self.assertEqual(prepaid['source'], 'billavenue_config')

    def test_inactive_category_falls_back(self):
        BbpsCategoryWalletCharge.objects.create(
            category_code='water',
            mode='FLAT',
            flat=Decimal('40'),
            percent=Decimal('0'),
            is_active=False,
        )
        info = resolve_bbps_wallet_service_charge(amount=Decimal('200'), category_code='water')
        self.assertEqual(info['charge'], Decimal('5.00'))
        self.assertEqual(info['source'], 'billavenue_config')

    def test_mobile_recharge_alias_is_postpaid_not_prepaid(self):
        BbpsCategoryWalletCharge.objects.create(
            category_code='mobile-prepaid',
            mode='FLAT',
            flat=Decimal('15'),
            percent=Decimal('0'),
            is_active=True,
        )
        BbpsCategoryWalletCharge.objects.create(
            category_code='mobile-postpaid',
            mode='FLAT',
            flat=Decimal('3'),
            percent=Decimal('0'),
            is_active=True,
        )
        info = resolve_bbps_wallet_service_charge(amount=Decimal('100'), category_code='mobile-recharge')
        self.assertEqual(info['category_code'], 'mobile-postpaid')
        self.assertEqual(info['charge'], Decimal('3.00'))
        self.assertEqual(info['category_name'], 'Mobile Postpaid')

    def test_saving_category_does_not_rewrite_past_payment(self):
        payment = BillPayment.objects.create(
            user=self.retailer,
            biller='Old Board',
            biller_id='OLD1',
            bill_type='electricity',
            amount=Decimal('500'),
            charge=Decimal('5'),
            total_deducted=Decimal('505'),
            service_id='OLD-ELEC-1',
            status='SUCCESS',
        )
        client = APIClient()
        client.force_authenticate(user=self.admin)
        res = client.patch(
            '/api/bbps/admin/wallet-charges/',
            {
                'category_code': 'electricity',
                'mode': 'FLAT',
                'flat': '25',
                'percent': '0',
                'is_active': True,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        payment.refresh_from_db()
        self.assertEqual(payment.charge, Decimal('5.0000'))

    def test_quote_uses_category_charge(self):
        BbpsCategoryWalletCharge.objects.create(
            category_code='dth',
            mode='FLAT',
            flat=Decimal('12'),
            percent=Decimal('0'),
            is_active=True,
        )
        client = APIClient()
        client.force_authenticate(user=self.retailer)
        res = client.post(
            '/api/bbps/quote/',
            {'amount': '200', 'biller_id': 'DTH1', 'bill_type': 'dth'},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        data = res.json()['data']
        self.assertEqual(data['applied_charge'], 12.0)
        self.assertEqual(data['wallet_service_charge_source'], 'category')
        self.assertEqual(data['wallet_service_charge_category_name'], 'DTH')

    def test_payment_snapshots_category_charge(self):
        BbpsCategoryWalletCharge.objects.create(
            category_code='electricity',
            mode='PERCENT',
            flat=Decimal('0'),
            percent=Decimal('10'),
            is_active=True,
        )
        BbpsBillerMaster.objects.create(
            environment='prod',
            biller_id='ELECCHARGE1',
            biller_name='City Power',
            biller_category='Electricity',
            biller_status='ACTIVE',
            is_active_local=True,
        )
        wallet = Wallet.get_wallet(self.retailer, 'main')
        wallet.balance = Decimal('100000')
        wallet.held_balance = Decimal('0')
        wallet.save(update_fields=['balance', 'held_balance'])

        def _stop(**kwargs):
            return {
                'attempt': kwargs['attempt'],
                'bill_payment': kwargs['bill_payment'],
                'idempotent': False,
            }

        with patch('apps.bbps.service_flow.payment_service.validate_channel_device_fields'), \
             patch('apps.bbps.service_flow.payment_service.enforce_biller_mode_channel_constraints'), \
             patch('apps.bbps.service_flow.payment_service.enforce_plan_mdm_requirement'), \
             patch('apps.bbps.service_flow.payment_service.enforce_fetch_pay_linkage', return_value=None), \
             patch('apps.bbps.service_flow.payment_service.enforce_payment_amount_policy'), \
             patch('apps.bbps.service_flow.payment_service.enforce_cash_pan_rule'), \
             patch('apps.bbps.service_flow.payment_service.assert_float_available'), \
             patch('apps.bbps.service_flow.payment_service.compute_ccf1_if_required', return_value=None), \
             patch(
                 'apps.bbps.service_flow.payment_service.resolve_commission_for_payment',
                 return_value={'charge': 0, 'computed_charge': 0, 'commission_rule_code': '', 'commission_rule_snapshot': {}},
             ), \
             patch('apps.bbps.service_flow.validation_service.validate_biller_inputs', return_value=[]), \
             patch('apps.bbps.service_flow.payment_service.BBPSClient') as client_cls, \
             patch('apps.bbps.service_flow.user_wallet_settlement.place_payment_hold'), \
             patch('apps.bbps.service_flow.payment_service._finalize_pay_result', side_effect=_stop):
            client_cls.return_value._build_bill_payment_payload.return_value = {}
            client_cls.return_value.process_payment.return_value = {
                'status': 'AWAITED',
                'message': 'ok',
                'txn_ref_id': '',
                'approval_ref_number': '',
                'response_payload': {},
            }
            from apps.bbps.service_flow.payment_service import process_bill_payment_flow

            process_bill_payment_flow(
                user=self.retailer,
                bill_data={
                    'amount': '1000',
                    'biller_id': 'ELECCHARGE1',
                    'biller': 'City Power',
                    'bill_type': 'electricity',
                    'payment_mode': 'UPI',
                    'init_channel': 'AGT',
                    'service_id': 'SVC-ELEC-CHARGE-1',
                    'request_id': 'REQ-ELEC-CHARGE-1',
                    'input_params': [],
                    'agent_device_info': {'ip': '127.0.0.1', 'mac': '00:11:22:33:44:55'},
                    'customer_info': {'customerMobile': '9999999999'},
                },
            )

        payment = BillPayment.objects.get(service_id='SVC-ELEC-CHARGE-1')
        self.assertEqual(payment.charge, Decimal('100.0000'))
        self.assertEqual(payment.total_deducted, Decimal('1100.0000'))


@override_settings(BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED=False)
class BillAvenueSettingsAccessTests(TestCase):
    def setUp(self):
        seed_modules_and_permissions()
        self.admin = _user(phone='9100002001', email='set.admin@example.com', role='Admin', user_id='SETADMIN1')
        self.super = _user(phone='9100002002', email='set.super@example.com', role='Super Admin', user_id='SETSUPER1')
        cfg = get_or_create_billavenue_mode_row('prod')
        cfg.enabled = True
        cfg.bbps_wallet_service_charge_mode = 'FLAT'
        cfg.bbps_wallet_service_charge_flat = Decimal('9.0000')
        cfg.bbps_wallet_service_charge_percent = Decimal('0')
        cfg.access_code = 'ACCESS'
        cfg.institute_id = 'INST'
        cfg.save()
        activate_billavenue_config(cfg, user=self.super)
        self.cfg = cfg
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin)
        self.super_client = APIClient()
        self.super_client.force_authenticate(user=self.super)

    def test_admin_settings_module_seeds_disabled(self):
        row = RoleModulePermission.objects.get(role='Admin', module_code='bbps_settings')
        self.assertFalse(row.enabled)
        console = RoleModulePermission.objects.get(role='Admin', module_code='bbps_console')
        self.assertTrue(console.enabled)

    def test_admin_cannot_read_config_secrets_or_activate_until_enabled(self):
        self.assertEqual(self.admin_client.get('/api/bbps/admin/config/').status_code, 403)
        self.assertEqual(
            self.admin_client.post('/api/bbps/admin/config/secrets/', {'mode': 'prod'}, format='json').status_code,
            403,
        )
        self.assertEqual(
            self.admin_client.post('/api/bbps/admin/config/activate/', {'mode': 'prod'}, format='json').status_code,
            403,
        )
        charges = self.admin_client.get('/api/bbps/admin/wallet-charges/')
        self.assertEqual(charges.status_code, 200, charges.content)
        self.assertTrue(any(row['category_code'] == 'mobile-prepaid' for row in charges.json()['data']['categories']))

    def test_super_admin_can_read_config_and_charges(self):
        self.assertEqual(self.super_client.get('/api/bbps/admin/config/?mode=prod').status_code, 200)
        self.assertEqual(self.super_client.get('/api/bbps/admin/wallet-charges/').status_code, 200)

    def test_config_save_does_not_overwrite_charge(self):
        res = self.super_client.post(
            '/api/bbps/admin/config/',
            {
                'mode': 'prod',
                'access_code': 'ACCESS-2',
                'institute_id': 'INST',
                'base_url': 'https://api.billavenue.com',
                'bbps_wallet_service_charge_mode': 'PERCENT',
                'bbps_wallet_service_charge_flat': '1',
                'bbps_wallet_service_charge_percent': '9',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.cfg.refresh_from_db()
        self.assertEqual(self.cfg.access_code, 'ACCESS-2')
        self.assertEqual(self.cfg.bbps_wallet_service_charge_mode, 'FLAT')
        self.assertEqual(self.cfg.bbps_wallet_service_charge_flat, Decimal('9.0000'))

    def test_admin_can_update_default_and_category(self):
        default_res = self.admin_client.patch(
            '/api/bbps/admin/wallet-charges/',
            {'default': {'mode': 'FLAT', 'flat': '7.5', 'percent': '0'}},
            format='json',
        )
        self.assertEqual(default_res.status_code, 200, default_res.content)
        self.cfg.refresh_from_db()
        self.assertEqual(self.cfg.bbps_wallet_service_charge_flat, Decimal('7.5000'))

        cat_res = self.admin_client.patch(
            '/api/bbps/admin/wallet-charges/',
            {
                'category_code': 'mobile prepaid',
                'mode': 'PERCENT',
                'flat': '0',
                'percent': '1.25',
                'is_active': True,
            },
            format='json',
        )
        self.assertEqual(cat_res.status_code, 200, cat_res.content)
        row = BbpsCategoryWalletCharge.objects.get(category_code='mobile-prepaid')
        self.assertEqual(row.percent, Decimal('1.2500'))
        self.assertTrue(row.is_active)

    def test_enabling_role_module_lets_admin_open_settings(self):
        RoleModulePermission.objects.filter(role='Admin', module_code='bbps_settings').update(enabled=True)
        from django.core.cache import cache
        cache.clear()
        self.assertEqual(self.admin_client.get('/api/bbps/admin/config/?mode=prod').status_code, 200)
