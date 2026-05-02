from django.test import SimpleTestCase

from apps.bbps.views import _friendly_fetch_error_message, _friendly_plan_pull_error_message


class BbpsErrorMappingTests(SimpleTestCase):
    def test_fetch_timeout_message_is_friendly(self):
        msg = _friendly_fetch_error_message(
            'BBPS Service Error: TIMEOUT endpoint=bill_fetch connect=5s read=25s: Read timed out'
        )
        self.assertEqual(msg, 'Provider response timed out. Please retry in a few seconds.')

    def test_fetch_bfr004_keeps_no_due_mapping(self):
        msg = _friendly_fetch_error_message(
            '{"billFetchResponse":{"errorInfo":{"error":{"errorCode":"BFR004","errorMessage":"Payment received for the billing period - no bill due"}}}}'
        )
        self.assertEqual(msg, 'No bill is currently due for this account.')

    def test_plan_pull_timeout_message_is_friendly(self):
        msg = _friendly_plan_pull_error_message('requests.exceptions.Timeout: timed out')
        self.assertEqual(
            msg,
            'Plan service response timed out. Please retry. If this continues, verify BillAvenue timeout settings.',
        )
