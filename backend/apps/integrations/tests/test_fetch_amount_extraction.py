from decimal import Decimal

from django.test import SimpleTestCase

from apps.integrations.bbps_client import (
    additional_info_to_rupees,
    bill_amount_paise_to_rupees,
    extract_fetch_amount_fields,
)


class FetchAmountExtractionTests(SimpleTestCase):
    def test_bill_amount_paise_to_rupees(self):
        self.assertEqual(bill_amount_paise_to_rupees('4770472'), Decimal('47704.72'))

    def test_additional_info_decimal_is_rupees(self):
        self.assertEqual(
            additional_info_to_rupees('3151.99', bill_amount_rupees=Decimal('47704.72')),
            Decimal('3151.99'),
        )

    def test_additional_info_whole_rupee_max_not_divided(self):
        self.assertEqual(
            additional_info_to_rupees('50000', bill_amount_rupees=Decimal('37855.28')),
            Decimal('50000'),
        )

    def test_additional_info_integer_matching_bill_paise(self):
        self.assertEqual(
            additional_info_to_rupees('3785528', bill_amount_rupees=Decimal('37855.28')),
            Decimal('37855.28'),
        )

    def test_sbi_style_min_max_only_uses_bill_amount_as_total(self):
        out = extract_fetch_amount_fields(
            bill_response={
                'billAmount': '4770472',
                'customerName': 'PYDIGANTAM SAI KUMAR',
                'dueDate': '2026-08-27',
            },
            normalized={},
            additional_info_rows=[
                {'infoName': 'Minimum Amount Due', 'infoValue': '3151.99'},
                {'infoName': 'Maximum Permissible Amount', 'infoValue': '55400.53'},
            ],
        )
        self.assertEqual(out['bill_amount'], '47704.72')
        self.assertEqual(out['minimum_due'], '3151.99')
        self.assertEqual(out['total_due'], '47704.72')
        self.assertEqual(out['maximum_payable'], '55400.53')
        self.assertEqual(out['amounts']['total_due'], '47704.72')

    def test_electricity_due_amount_alias(self):
        out = extract_fetch_amount_fields(
            bill_response={'billAmount': '37600', 'customerName': 'CHANDRA'},
            normalized={},
            additional_info_rows=[
                {'infoName': 'Due amount', 'infoValue': '376.0'},
                {'infoName': 'Reconnection Charges', 'infoValue': '0.0'},
            ],
        )
        self.assertEqual(out['amount'], Decimal('376.00'))
        self.assertEqual(out['total_due'], '376.0')
        self.assertEqual(out['minimum_due'], '0')

    def test_outstanding_alias_preferred_over_bill_amount(self):
        out = extract_fetch_amount_fields(
            bill_response={'billAmount': '100000'},
            normalized={},
            additional_info_rows=[
                {'infoName': 'Current Outstanding Amount', 'infoValue': '1200.50'},
                {'infoName': 'Minimum Amount Due', 'infoValue': '200.00'},
            ],
        )
        self.assertEqual(out['total_due'], '1200.50')
        self.assertEqual(out['minimum_due'], '200.00')
        self.assertEqual(Decimal(out['bill_amount']), Decimal('1000'))

    def test_integer_min_due_is_rupees_not_paise(self):
        """Provider additionalInfo integers are rupees (e.g. 37856 → ₹37,856)."""
        out = extract_fetch_amount_fields(
            bill_response={'billAmount': '3785528', 'customerName': 'Customer'},
            normalized={},
            additional_info_rows=[
                {'infoName': 'Minimum due amount', 'infoValue': '37856'},
                {'infoName': 'Maximum Permissible Amount', 'infoValue': '50000'},
            ],
        )
        self.assertEqual(Decimal(out['bill_amount']), Decimal('37855.28'))
        self.assertEqual(Decimal(out['minimum_due']), Decimal('37856'))
        self.assertEqual(Decimal(out['maximum_payable']), Decimal('50000'))
        self.assertEqual(Decimal(out['total_due']), Decimal('37855.28'))
