"""BBPS payment channel vs mode (NPCI-aligned) and biller schema payment UI hints."""
from decimal import Decimal

from django.test import TestCase

from apps.bbps.models import BbpsBillerMaster, BbpsBillerPaymentChannelLimit, BbpsBillerPaymentModeLimit
from apps.bbps.services import get_biller_payment_ui_options
from apps.bbps.service_flow.compliance import (
    display_payment_modes_for_channel,
    enforce_biller_mode_channel_constraints,
)
from apps.core.exceptions import TransactionFailed


class BbpsPaymentChannelModeUiTests(TestCase):
    def test_display_modes_filters_upi_on_agt_when_mdm_lists_upi(self):
        modes = display_payment_modes_for_channel('AGT', ['UPI', 'Cash', 'Debit Card'])
        self.assertIn('Cash', modes)
        self.assertNotIn('Debit Card', modes)
        self.assertNotIn('UPI', modes)

    def test_display_modes_mob_includes_upi(self):
        modes = display_payment_modes_for_channel('MOB', ['UPI', 'Cash'])
        self.assertIn('UPI', modes)

    def test_get_biller_payment_ui_options_defaults(self):
        biller = BbpsBillerMaster.objects.create(
            biller_id='UIELEC01',
            biller_name='UI Test',
            biller_category='electricity',
            biller_status='ACTIVE',
        )
        out = get_biller_payment_ui_options('UIELEC01')
        self.assertEqual(out['default_channel'], 'AGT')
        self.assertIn('Cash', out['payment_modes_by_channel'].get('AGT', []))
        self.assertIn('Cash', out['payment_modes'])
        self.assertEqual(out['payment_mode_channel_map'].get('Cash'), 'AGT')

    def test_get_biller_payment_ui_options_no_terminal_safe_mode(self):
        biller = BbpsBillerMaster.objects.create(
            biller_id='UIELEC02',
            biller_name='UI Test 2',
            biller_category='electricity',
            biller_status='ACTIVE',
        )
        BbpsBillerPaymentChannelLimit.objects.create(
            biller=biller, payment_channel='INT', min_amount=0, max_amount=0
        )
        BbpsBillerPaymentModeLimit.objects.create(
            biller=biller, payment_mode='Credit Card', min_amount=0, max_amount=0
        )
        out = get_biller_payment_ui_options('UIELEC02')
        self.assertEqual(out['payment_modes'], [])
        self.assertEqual(out['payment_mode_channel_map'], {})
        self.assertEqual(out['source'], 'requires_device_context')


class BbpsModeChannelComplianceTests(TestCase):
    def test_mode_channel_matrix_validation(self):
        biller = BbpsBillerMaster.objects.create(
            biller_id='CC2001',
            biller_name='Test Biller',
            biller_category='credit-card',
            biller_status='ACTIVE',
        )
        BbpsBillerPaymentChannelLimit.objects.create(biller=biller, payment_channel='AGT', min_amount=0, max_amount=0)
        BbpsBillerPaymentModeLimit.objects.create(biller=biller, payment_mode='UPI', min_amount=0, max_amount=0)
        BbpsBillerPaymentModeLimit.objects.create(biller=biller, payment_mode='Cash', min_amount=0, max_amount=0)
        with self.assertRaises(TransactionFailed):
            enforce_biller_mode_channel_constraints(
                biller=biller,
                payment_mode='UPI',
                payment_channel='AGT',
                amount=Decimal('10'),
            )
        enforce_biller_mode_channel_constraints(
            biller=biller,
            payment_mode='Cash',
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
