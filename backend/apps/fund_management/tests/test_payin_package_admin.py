"""Pay-in package admin serializer and per-rail fee tests."""
from decimal import Decimal

from django.test import TestCase

from apps.admin_panel.models import PaymentGateway
from apps.admin_panel.serializers import PayInPackageAdminSerializer
from apps.fund_management.models import PayInPackage, PayInQrAccount
from apps.fund_management.rail_fees import resolve_rail_gateway_fee_pct


class PayInPackageCreateWithQrTests(TestCase):
    def setUp(self):
        self.gateway = PaymentGateway.objects.create(
            name='Razorpay Test',
            charge_rate=Decimal('1.00'),
            status='active',
            visible_to_roles=['Admin'],
        )
        self.qr = PayInQrAccount.objects.create(
            display_name='QR 1',
            charge_rate=Decimal('0.50'),
            status='active',
        )

    def test_create_with_qr_account_ids_succeeds(self):
        ser = PayInPackageAdminSerializer(
            data={
                'code': 'test_pkg_qr',
                'display_name': 'Test QR Package',
                'payment_gateway_ids': [self.gateway.pk],
                'default_payment_gateway_id': self.gateway.pk,
                'payment_gateway_id': self.gateway.pk,
                'qr_account_ids': [self.qr.pk],
                'default_qr_account_id': self.qr.pk,
                'min_amount': '1',
                'max_amount_per_txn': '100000',
                'package_gateways': [
                    {'id': self.gateway.pk, 'gateway_fee_pct': '1.0000'},
                ],
                'admin_pct': '0.2400',
                'super_distributor_pct': '0.0100',
                'master_distributor_pct': '0.0200',
                'distributor_pct': '0.0300',
                'is_active': True,
                'sort_order': 0,
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        pkg = ser.save()
        self.assertEqual(pkg.package_qr_links.count(), 1)
        link = pkg.package_qr_links.first()
        self.assertEqual(link.qr_account_id, self.qr.pk)

    def test_create_qr_only_package_succeeds(self):
        ser = PayInPackageAdminSerializer(
            data={
                'code': 'qr_only_pkg',
                'display_name': 'QR Only Package',
                'payment_gateway_ids': [],
                'qr_account_ids': [self.qr.pk],
                'default_qr_account_id': self.qr.pk,
                'min_amount': '1',
                'max_amount_per_txn': '100000',
                'package_qr_accounts': [
                    {'id': self.qr.pk, 'gateway_fee_pct': '0.5000'},
                ],
                'admin_pct': '0.2400',
                'super_distributor_pct': '0.0100',
                'master_distributor_pct': '0.0200',
                'distributor_pct': '0.0300',
                'is_active': True,
                'sort_order': 0,
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        pkg = ser.save()
        self.assertEqual(pkg.package_qr_links.count(), 1)
        self.assertEqual(pkg.package_gateways.filter(is_deleted=False).count(), 0)
        self.assertIsNone(pkg.payment_gateway_id)

    def test_rejects_gateway_fee_below_charge_rate(self):
        ser = PayInPackageAdminSerializer(
            data={
                'code': 'low_fee_pkg',
                'display_name': 'Low fee',
                'payment_gateway_ids': [self.gateway.pk],
                'default_payment_gateway_id': self.gateway.pk,
                'package_gateways': [
                    {'id': self.gateway.pk, 'gateway_fee_pct': '0.5000'},
                ],
                'qr_account_ids': [],
                'min_amount': '1',
                'max_amount_per_txn': '100000',
                'admin_pct': '0.2400',
                'super_distributor_pct': '0.0100',
                'master_distributor_pct': '0.0200',
                'distributor_pct': '0.0300',
                'is_active': True,
                'sort_order': 0,
            }
        )
        self.assertFalse(ser.is_valid())
        self.assertIn('package_gateways', ser.errors)

    def test_create_derives_gateway_fee_pct_from_rail_fees(self):
        ser = PayInPackageAdminSerializer(
            data={
                'code': 'auto_gw_fee',
                'display_name': 'Auto GW fee',
                'payment_gateway_ids': [self.gateway.pk],
                'default_payment_gateway_id': self.gateway.pk,
                'package_gateways': [
                    {'id': self.gateway.pk, 'gateway_fee_pct': '1.5000'},
                ],
                'qr_account_ids': [self.qr.pk],
                'package_qr_accounts': [
                    {'id': self.qr.pk, 'gateway_fee_pct': '0.7500'},
                ],
                'min_amount': '1',
                'max_amount_per_txn': '100000',
                'admin_pct': '0.2400',
                'super_distributor_pct': '0.0100',
                'master_distributor_pct': '0.0200',
                'distributor_pct': '0.0300',
                'is_active': True,
                'sort_order': 0,
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        pkg = ser.save()
        self.assertEqual(pkg.gateway_fee_pct, Decimal('1.5000'))
        data = PayInPackageAdminSerializer(pkg).data
        self.assertEqual(Decimal(str(data['max_rail_gateway_fee_pct'])), Decimal('1.5000'))

    def test_resolve_rail_gateway_fee_uses_link_override(self):
        pkg = PayInPackage.objects.create(
            code='rail_fee_pkg',
            display_name='Rail fee',
            payment_gateway=self.gateway,
            provider='razorpay',
            gateway_fee_pct=Decimal('1.0000'),
            admin_pct=Decimal('0.24'),
        )
        from apps.fund_management.package_gateways import sync_package_gateway_links
        from apps.fund_management.package_qr_accounts import sync_package_qr_links

        sync_package_gateway_links(
            pkg,
            [self.gateway.pk],
            gateway_fees={self.gateway.pk: Decimal('1.5000')},
        )
        sync_package_qr_links(
            pkg,
            [self.qr.pk],
            qr_fees={self.qr.pk: Decimal('0.7500')},
        )
        self.assertEqual(
            resolve_rail_gateway_fee_pct(pkg, gateway_id=self.gateway.pk),
            Decimal('1.5000'),
        )
        self.assertEqual(
            resolve_rail_gateway_fee_pct(pkg, qr_account_id=self.qr.pk),
            Decimal('0.7500'),
        )
