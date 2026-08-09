from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.bbps.service_flow.fetch_service import resolve_presentation_mode


class PresentationModeTests(SimpleTestCase):
    def test_amount_load_for_not_supported(self):
        master = SimpleNamespace(biller_adhoc=True, plan_mdm_requirement='NOT_SUPPORTED')
        mode = resolve_presentation_mode(
            master=master,
            result={'flow': 'adhoc_validate', 'biller_adhoc': True},
            fetch_not_supported=True,
        )
        self.assertEqual(mode, 'amount_load')

    def test_plan_mode_when_plan_mdm_mandatory(self):
        master = SimpleNamespace(biller_adhoc=False, plan_mdm_requirement='MANDATORY')
        mode = resolve_presentation_mode(
            master=master,
            result={'biller_adhoc': False, 'amount': 0},
            fetch_not_supported=False,
        )
        self.assertEqual(mode, 'plan')

    def test_bill_fetch_adhoc_for_credit_card(self):
        master = SimpleNamespace(biller_adhoc=True, plan_mdm_requirement='NOT_SUPPORTED')
        mode = resolve_presentation_mode(
            master=master,
            result={'biller_adhoc': True, 'amount': 37855.28},
            fetch_not_supported=False,
        )
        self.assertEqual(mode, 'bill_fetch_adhoc')

    def test_bill_fetch_for_standard_utility(self):
        master = SimpleNamespace(biller_adhoc=False, plan_mdm_requirement='')
        mode = resolve_presentation_mode(
            master=master,
            result={'biller_adhoc': False, 'amount': 376},
            fetch_not_supported=False,
        )
        self.assertEqual(mode, 'bill_fetch')
