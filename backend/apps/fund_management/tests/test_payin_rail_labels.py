"""Pay-in rail label helpers."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.fund_management.models import LoadMoney, PayInPackage, PayInQrAccount
from apps.fund_management.payin_rail_labels import (
    payin_collection_method_label,
    payin_gateway_provider_name,
    payin_is_qr_rail,
    payin_rail_type_label,
)


class PayinRailLabelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            phone='9555555501',
            email='rail@test.com',
            password='testpass123',
            role='Retailer',
            user_id='RAIL01',
            first_name='R',
            last_name='User',
        )
        self.pkg = PayInPackage.objects.create(
            code='rail_pkg',
            display_name='Razorpay Package',
            provider='razorpay',
            gateway_fee_pct=Decimal('1.0000'),
            admin_pct=Decimal('0.2400'),
            super_distributor_pct=Decimal('0.0100'),
            master_distributor_pct=Decimal('0.0200'),
            distributor_pct=Decimal('0.0300'),
            retailer_commission_pct=Decimal('0.0000'),
            min_amount=Decimal('1'),
            max_amount_per_txn=Decimal('200000'),
            sort_order=0,
        )
        self.qr = PayInQrAccount.objects.create(
            display_name='QR 1',
            account_display_name='Test',
            upi_vpa='test@upi',
            status='active',
            daily_limit_24h=Decimal('100000'),
            sort_order=0,
        )

    def test_qr_row_uses_qr_account_not_package_gateway(self):
        lm = LoadMoney.objects.create(
            user=self.user,
            package=self.pkg,
            amount=Decimal('1000'),
            gateway='QR 1',
            charge=Decimal('0'),
            net_credit=Decimal('0'),
            status='SUCCESS',
            collection_rail='qr',
            pay_in_qr_account=self.qr,
            utr='UTRQR01',
        )
        self.assertTrue(payin_is_qr_rail(lm))
        self.assertEqual(payin_collection_method_label(lm), 'QR 1')
        self.assertEqual(payin_rail_type_label(lm), 'Manual QR')
        self.assertNotEqual(payin_collection_method_label(lm), 'Razorpay')

    def test_gateway_row_uses_provider_name(self):
        lm = LoadMoney.objects.create(
            user=self.user,
            package=self.pkg,
            amount=Decimal('500'),
            gateway='razorpay',
            charge=Decimal('0'),
            net_credit=Decimal('0'),
            status='SUCCESS',
            collection_rail='gateway',
        )
        self.assertFalse(payin_is_qr_rail(lm))
        self.assertEqual(payin_gateway_provider_name(lm), 'Razorpay')
        self.assertEqual(payin_rail_type_label(lm), 'Payment Gateway')
