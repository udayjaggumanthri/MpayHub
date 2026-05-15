from django.test import SimpleTestCase

from apps.bbps.views import (
    _friendly_complaint_error_message,
    _friendly_fetch_error_message,
    _friendly_pay_error_message,
    _friendly_plan_pull_error_message,
)


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

    def test_pay_code_204_message_is_friendly(self):
        msg = _friendly_pay_error_message(
            'BillAvenue API failed (bill_pay) code=204 ({"ExtBillPayResponse": {"responseCode": "204", '
            '"errorInfo": {"error": {"errorCode": "E204", "errorMessage": "Request Id is already been used."}}}})'
        )
        self.assertIn('Fetch the bill again', msg)

    def test_pay_e078_message_is_friendly(self):
        msg = _friendly_pay_error_message(
            '{"errorCode":"E078","errorMessage":"Payment Channel:POS invalid for AI:PI39"}'
        )
        self.assertIn('AGT', msg)

    def test_pay_outer_204_with_e212_not_treated_as_fetch_consumed(self):
        raw = (
            'BillAvenue API failed (bill_pay) code=204 ({"ExtBillPayResponse": {"responseCode": "204", '
            '"errorInfo": {"error": {"errorCode": "E212", "errorMessage": "additionalInfo value mismatch."}}}})'
        )
        msg = _friendly_pay_error_message(raw)
        self.assertIn('additionalInfo', msg)
        self.assertNotIn('already consumed', msg.lower())

    def test_complaint_v5004_message_is_friendly(self):
        msg = _friendly_complaint_error_message(
            'BillAvenue API failed (complaint_register) code=205 {"errorCode":"V5004","errorMessage":"Description missing"}'
        )
        self.assertIn('description was rejected', msg.lower())

    def test_complaint_register_code_001_unable_to_process_is_friendly(self):
        raw = (
            'BillAvenue API failed (complaint_register) code=001 ({"complaintResponseCode": "001", '
            '"complaintResponseReason": "Sorry, we were unable to process your request against Transaction Id  : CC01."})'
        )
        msg = _friendly_complaint_error_message(raw)
        self.assertIn('BillAvenue did not accept', msg)
        self.assertIn('CC', msg)

    def test_complaint_register_code_001_existing_ticket_is_friendly(self):
        raw = (
            'BillAvenue API failed (complaint_register) code=001 ({"complaintResponseCode": "001", '
            '"complaintResponseReason": "Sorry, we are unable to raise a new ticket for transaction ID : CC01."})'
        )
        msg = _friendly_complaint_error_message(raw)
        self.assertIn('already exist', msg.lower())
        self.assertIn('Complaint Tracking', msg)

    def test_complaint_register_code_205_is_friendly(self):
        msg = _friendly_complaint_error_message('BillAvenue API failed (complaint_register) code=205 (FAILURE)')
        self.assertIn('205', msg)
        self.assertIn('BillAvenue', msg)
