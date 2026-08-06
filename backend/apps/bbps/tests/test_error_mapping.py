from django.test import SimpleTestCase

from apps.bbps.error_catalog import resolve_bbps_error
from apps.bbps.views import (
    _friendly_complaint_error_message,
    _friendly_fetch_error_message,
    _friendly_pay_error_message,
    _friendly_plan_pull_error_message,
)


class BbpsErrorMappingTests(SimpleTestCase):
    def test_pay_timeout_message_is_friendly(self):
        msg = _friendly_pay_error_message(
            'TIMEOUT endpoint=bill_pay connect=10s read=20s: HTTPSConnectionPool(host=\'stgapi.billavenue.com\', port=443): Read timed out.'
        )
        self.assertIn('try again', msg.lower())

    def test_fetch_timeout_message_is_friendly(self):
        msg = _friendly_fetch_error_message(
            'BBPS Service Error: TIMEOUT endpoint=bill_fetch connect=5s read=25s: Read timed out'
        )
        self.assertEqual(msg, 'Provider response timed out. Please retry in a few seconds.')

    def test_fetch_agent_id_invalid_is_friendly(self):
        msg = _friendly_fetch_error_message(
            'BillAvenue API failed (bill_validate) code=200 (VE003 — Agent ID invalid)'
        )
        self.assertIn('Agent ID', msg)
        self.assertIn('BillAvenue Settings', msg)

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

    def test_e135_raw_json_never_leaks(self):
        raw = '{"errorCode":"E135","errorMessage":"Mandatory Input Parameter Not Present or mismatch"}'
        info = resolve_bbps_error(raw, endpoint='bill_fetch')
        self.assertEqual(info.provider_code, 'E135')
        self.assertEqual(info.category, 'input_validation')
        self.assertNotIn('{"errorCode"', info.user_message)
        self.assertIn('highlighted fields', info.user_message.lower())

    def test_um001_and_bfr006_and_ve_codes(self):
        um = resolve_bbps_error('{"errorCode":"UM001","errorMessage":"Invalid Request"}', endpoint='bill_fetch')
        self.assertEqual(um.provider_code, 'UM001')
        self.assertNotIn('{"errorCode"', um.user_message)

        bfr = resolve_bbps_error(
            'BillAvenue API failed (bill_fetch) code=200 ({"errorCode":"BFR006","errorMessage":"Unable to get bill details"})',
            endpoint='bill_fetch',
        )
        self.assertEqual(bfr.provider_code, 'BFR006')
        self.assertEqual(bfr.category, 'account')

        ve9 = resolve_bbps_error('VE009', endpoint='bill_fetch')
        self.assertEqual(ve9.provider_code, 'VE009')
        self.assertEqual(ve9.category, 'input_validation')
        ve10 = resolve_bbps_error('code=200 (VE010 — param too long)', endpoint='bill_fetch')
        self.assertEqual(ve10.provider_code, 'VE010')

    def test_ve013_mandatory_param_not_mapped_as_duplicate(self):
        raw = (
            'BillAvenue API failed (bill_validate) code=200 '
            '(VE013 — Mandatory Input Parameter Not Present or mismatch)'
        )
        info = resolve_bbps_error(raw, endpoint='bill_fetch')
        self.assertEqual(info.category, 'input_validation')
        self.assertNotIn('Duplicate request', info.user_message)
        self.assertIn('highlighted fields', info.user_message.lower())
