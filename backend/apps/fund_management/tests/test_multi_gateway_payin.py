"""Multi-gateway pay-in: package links, gateway resolution, fee invariance, verify credentials."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.admin_panel.models import PaymentGateway
from apps.contacts.models import Contact
from apps.fund_management.models import LoadMoney, PayInPackage, UserPackageAssignment
from apps.fund_management.package_gateways import (
    list_payin_checkout_options_for_user,
    resolve_payment_gateway_for_order,
    serialize_package_gateways,
    sync_package_gateway_links,
)
from apps.fund_management.services import (
    _api_master_for_payin_razorpay,
    create_payin_order,
    quote_payin,
)
from apps.integrations.models import ApiMaster

User = get_user_model()


def _make_gateway(name, *, api_master=None, status='active'):
    return PaymentGateway.objects.create(
        name=name,
        charge_rate=Decimal('1.00'),
        status=status,
        visible_to_roles=['Retailer'],
        api_master=api_master,
    )


def _make_razorpay_master(code):
    return ApiMaster.objects.create(
        provider_code=code,
        provider_name=code,
        provider_type='payments',
        status='active',
    )


def _make_package(code='mgw_pkg', provider='mock'):
    return PayInPackage.objects.create(
        code=code,
        display_name=code,
        provider=provider,
        gateway_fee_pct=Decimal('1.0000'),
        admin_pct=Decimal('0.2400'),
        super_distributor_pct=Decimal('0.0100'),
        master_distributor_pct=Decimal('0.0200'),
        distributor_pct=Decimal('0.0300'),
        retailer_commission_pct=Decimal('0.0000'),
        sort_order=0,
        is_default=False,
    )


class MultiGatewayPayInTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555501',
            email='mgw@test.com',
            password='testpass123',
            role='Retailer',
            user_id='MGW01',
            first_name='M',
            last_name='User',
        )
        self.contact = Contact.objects.create(
            user=self.user,
            name='Test Customer',
            email='cust@test.com',
            phone='9876543210',
        )
        self.am_a = _make_razorpay_master('razorpay_mgw_a')
        self.am_b = _make_razorpay_master('razorpay_mgw_b')
        self.gw_a = _make_gateway('Gateway A', api_master=self.am_a)
        self.gw_b = _make_gateway('Gateway B', api_master=self.am_b)
        self.package = _make_package()
        sync_package_gateway_links(
            self.package,
            [self.gw_a.id, self.gw_b.id],
            default_gateway_id=self.gw_a.id,
        )
        UserPackageAssignment.objects.create(user=self.user, package=self.package)

    def test_list_payin_checkout_options_across_assigned_packages(self):
        pkg_b = _make_package('mgw_pkg_b')
        gw_c = _make_gateway('Gateway C')
        sync_package_gateway_links(pkg_b, [gw_c.id], default_gateway_id=gw_c.id)
        UserPackageAssignment.objects.create(user=self.user, package=pkg_b)

        options = list_payin_checkout_options_for_user(self.user)
        keys = {row['option_key'] for row in options}
        self.assertEqual(
            keys,
            {
                f'{self.package.id}:{self.gw_a.id}',
                f'{self.package.id}:{self.gw_b.id}',
                f'{pkg_b.id}:{gw_c.id}',
            },
        )
        names = {row['name'] for row in options}
        self.assertEqual(names, {'Gateway A', 'Gateway B', 'Gateway C'})

    def test_serialize_package_gateways(self):
        data = serialize_package_gateways(self.package)
        self.assertEqual(len(data), 2)
        ids = {row['id'] for row in data}
        self.assertEqual(ids, {self.gw_a.id, self.gw_b.id})
        default = [row for row in data if row['is_default']]
        self.assertEqual(len(default), 1)
        self.assertEqual(default[0]['id'], self.gw_a.id)

    def test_resolve_rejects_unlinked_gateway(self):
        other = _make_gateway('Other')
        with self.assertRaises(ValueError) as ctx:
            resolve_payment_gateway_for_order(self.package, other.id)
        self.assertIn('not linked', str(ctx.exception))

    def test_resolve_rejects_inactive_gateway_on_package(self):
        from apps.fund_management.models import PayInPackageGateway

        PayInPackageGateway.objects.filter(
            package=self.package, payment_gateway=self.gw_b
        ).update(is_active=False)
        with self.assertRaises(ValueError) as ctx:
            resolve_payment_gateway_for_order(self.package, self.gw_b.id)
        self.assertIn('not available', str(ctx.exception))

    def test_create_payin_order_stores_selected_gateway(self):
        gross = Decimal('1000.00')
        lm, payload = create_payin_order(
            self.user,
            package_id=self.package.id,
            gross=gross,
            contact_id=self.contact.id,
            gateway_id=self.gw_b.id,
        )
        self.assertEqual(lm.payment_gateway_id, self.gw_b.id)
        self.assertEqual(payload['payment_gateway_id'], self.gw_b.id)
        self.assertEqual(payload['payment_gateway_name'], 'Gateway B')

    def test_quote_unchanged_when_switching_gateway(self):
        gross = Decimal('5000.00')
        q_default = quote_payin(self.package, gross, self.user)
        resolve_payment_gateway_for_order(self.package, self.gw_b.id)
        q_other = quote_payin(self.package, gross, self.user)
        self.assertEqual(q_default['net_credit'], q_other['net_credit'])
        self.assertEqual(q_default['total_deduction'], q_other['total_deduction'])

    def test_api_master_resolution_uses_selected_payment_gateway(self):
        pkg = _make_package('mgw_rz', provider='razorpay')
        pkg.payment_gateway = self.gw_a
        pkg.save(update_fields=['payment_gateway'])
        sync_package_gateway_links(pkg, [self.gw_a.id, self.gw_b.id], default_gateway_id=self.gw_a.id)

        self.assertEqual(
            _api_master_for_payin_razorpay(pkg, payment_gateway=self.gw_a).pk,
            self.am_a.pk,
        )
        self.assertEqual(
            _api_master_for_payin_razorpay(pkg, payment_gateway=self.gw_b).pk,
            self.am_b.pk,
        )

    @patch('apps.integrations.razorpay_orders.verify_razorpay_checkout_signature', return_value=True)
    @patch(
        'apps.integrations.razorpay_orders.fetch_razorpay_payment_until_captured',
        return_value=({'status': 'captured', 'order_id': 'order_xyz'}, None),
    )
    @patch('apps.fund_management.services._razorpay_keypair_for_payin_package')
    def test_verify_uses_load_money_payment_gateway_credentials(
        self, mock_keypair, _mock_fetch, _mock_verify_sig
    ):
        from apps.fund_management.services import verify_and_finalize_razorpay_payin

        mock_keypair.return_value = ('key_from_b', 'secret_from_b')

        pkg = _make_package('mgw_rz_verify', provider='razorpay')
        sync_package_gateway_links(pkg, [self.gw_a.id, self.gw_b.id], default_gateway_id=self.gw_a.id)
        lm = LoadMoney.objects.create(
            user=self.user,
            package=pkg,
            payment_gateway=self.gw_b,
            amount=Decimal('100.0000'),
            gateway=self.gw_b.name,
            charge=Decimal('5.0000'),
            net_credit=Decimal('95.0000'),
            customer_name='C',
            customer_email='c@test.com',
            customer_phone='9876543210',
            status='PENDING',
            transaction_id='LMGWTEST01',
            provider_order_id='order_xyz',
        )

        with patch('apps.fund_management.services.finalize_payin_success', return_value=lm):
            verify_and_finalize_razorpay_payin(
                self.user,
                transaction_id=lm.transaction_id,
                razorpay_order_id='order_xyz',
                razorpay_payment_id='pay_abc',
                razorpay_signature='sig',
            )

        mock_keypair.assert_called_once()
        _pkg_arg, kwargs = mock_keypair.call_args
        self.assertEqual(kwargs.get('payment_gateway'), self.gw_b)
