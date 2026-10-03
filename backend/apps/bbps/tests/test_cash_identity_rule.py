from django.test import SimpleTestCase

from apps.bbps.service_flow.compliance import enforce_cash_pan_rule
from apps.core.exceptions import TransactionFailed


class CashIdentityRuleTests(SimpleTestCase):
    def test_cash_requires_pan_or_aadhaar_plus_name(self):
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
        enforce_cash_pan_rule(
            amount_paise=5000000,
            payment_mode='Cash',
            customer_info={'customerAadhaar': '234567890123', 'customerName': 'Tarun I'},
        )
