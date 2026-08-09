from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.bbps.service_flow.compliance import (
    build_payment_amount_policy,
    enforce_payment_amount_policy,
)
from apps.core.exceptions import TransactionFailed


def _biller(*, adhoc=False, exactness=''):
    return SimpleNamespace(biller_adhoc=adhoc, biller_payment_exactness=exactness, biller_id='T1')


class PaymentAmountPolicyTests(SimpleTestCase):
    def test_adhoc_allows_custom_within_max(self):
        policy = build_payment_amount_policy(
            biller=_biller(adhoc=True),
            bill_amount_rupees='37855.28',
            minimum_due_rupees='0',
            additional_info_rows=[
                {'infoName': 'Minimum Amount Due', 'infoValue': '0'},
                {'infoName': 'Maximum Permissible Amount', 'infoValue': '50000'},
            ],
        )
        self.assertEqual(policy['mode'], 'adhoc')
        self.assertTrue(policy['allow_custom'])
        self.assertEqual(policy['max_amount'], '50000')
        enforce_payment_amount_policy(
            biller=_biller(adhoc=True),
            amount=Decimal('3000'),
            additional_info_rows=[
                {'infoName': 'Maximum Permissible Amount', 'infoValue': '50000'},
            ],
        )

    def test_adhoc_does_not_force_minimum_due_as_pay_floor(self):
        """Credit-card Minimum Due is informational; adhoc may pay any amount up to max."""
        policy = build_payment_amount_policy(
            biller=_biller(adhoc=True),
            bill_amount_rupees='47704.72',
            minimum_due_rupees='3151.99',
            maximum_payable_rupees='55400.53',
        )
        self.assertEqual(policy['mode'], 'adhoc')
        self.assertEqual(Decimal(policy['min_amount']), Decimal('0.01'))
        self.assertEqual(policy['minimum_due'], '3151.99')
        self.assertEqual(policy['max_amount'], '55400.53')
        enforce_payment_amount_policy(
            biller=_biller(adhoc=True),
            amount=Decimal('500'),
            additional_info_rows=[
                {'infoName': 'Minimum Amount Due', 'infoValue': '3151.99'},
                {'infoName': 'Maximum Permissible Amount', 'infoValue': '55400.53'},
            ],
        )

    def test_exact_rejects_custom(self):
        biller = _biller(adhoc=False, exactness='Exact')
        session = SimpleNamespace(amount_paise=100000, additional_info=[])
        with self.assertRaises(TransactionFailed):
            enforce_payment_amount_policy(
                biller=biller,
                amount=Decimal('500'),
                fetch_session=session,
            )

    def test_exact_and_below_allows_partial(self):
        biller = _biller(adhoc=False, exactness='Exact and below')
        session = SimpleNamespace(amount_paise=100000, additional_info=[])
        policy = enforce_payment_amount_policy(
            biller=biller,
            amount=Decimal('300'),
            fetch_session=session,
        )
        self.assertEqual(policy['mode'], 'exact_and_below')

    def test_exact_and_below_rejects_above_bill(self):
        biller = _biller(adhoc=False, exactness='Exact and below')
        session = SimpleNamespace(amount_paise=100000, additional_info=[])
        with self.assertRaises(TransactionFailed):
            enforce_payment_amount_policy(
                biller=biller,
                amount=Decimal('2000'),
                fetch_session=session,
            )
