"""Plan MDM Id injection for prepaid billers (e.g. BSNL)."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.bbps.catalog.persist_biller import persist_biller_from_mdm_row
from apps.bbps.service_flow.validation_service import (
    inject_plan_id_into_wire_list,
    validate_biller_inputs,
)
from apps.bbps.services import get_biller_input_schema
from apps.integrations.billavenue.registry import activate_billavenue_config, get_or_create_billavenue_mode_row

User = get_user_model()

BSNL_MDM = {
    'billerId': 'BSNL00000NATHL',
    'billerName': 'BSNL',
    'billerCategory': 'Mobile Prepaid',
    'billerStatus': 'ACTIVE',
    'billerAdhoc': 'true',
    'billerFetchRequiremet': 'NOT_SUPPORTED',
    'billerSupportBillValidation': 'MANDATORY',
    'planMdmRequirement': 'MANDATORY',
    'billerInputParams': {
        'paramInfo': [
            {
                'paramName': 'Circle',
                'isOptional': 'false',
                'visibility': 'true',
                'dataType': 'ALPHANUMERIC',
                'values': 'Andhra Pradesh,Assam',
            },
            {
                'paramName': 'Id',
                'isOptional': 'false',
                'visibility': 'false',
                'dataType': 'ALPHANUMERIC',
                'regEx': '^[A-Z0-9]{2,4}[A-Za-z]{5,8}[0-9]{1,4}$',
                'minLength': '7',
                'maxLength': '16',
            },
            {
                'paramName': 'Mobile Number',
                'isOptional': 'false',
                'visibility': 'true',
                'dataType': 'NUMERIC',
                'regEx': '^[6-9][0-9]{9}$',
                'minLength': '10',
                'maxLength': '10',
            },
        ]
    },
}


class PlanIdInjectionTests(TestCase):
    def setUp(self):
        prod = get_or_create_billavenue_mode_row('prod')
        prod.enabled = True
        prod.base_url = 'https://api.billavenue.com'
        prod.save()
        activate_billavenue_config(prod)
        persist_biller_from_mdm_row(BSNL_MDM, environment='prod')

    def test_schema_hides_plan_id_slot(self):
        rows = get_biller_input_schema('BSNL00000NATHL')
        names = {str(r.get('param_name') or '') for r in rows}
        self.assertIn('Circle', names)
        self.assertIn('Mobile Number', names)
        self.assertNotIn('Id', names)

    def test_validate_inputs_injects_plan_as_id_without_regex(self):
        wire = validate_biller_inputs(
            biller_id='BSNL00000NATHL',
            input_map={'Circle': 'Andhra Pradesh', 'Mobile Number': '9876543210'},
            plan_id='PLAN99XYZ',
        )
        by_name = {r['paramName']: r['paramValue'] for r in wire}
        self.assertEqual(by_name.get('Id'), 'PLAN99XYZ')
        self.assertEqual(by_name.get('Circle'), 'Andhra Pradesh')
        self.assertEqual(by_name.get('Mobile Number'), '9876543210')

    def test_wire_list_inject(self):
        rows = inject_plan_id_into_wire_list(
            biller_id='BSNL00000NATHL',
            wire=[{'paramName': 'Circle', 'paramValue': 'Assam'}],
            plan_id='ABC123',
        )
        by_name = {r['paramName']: r['paramValue'] for r in rows}
        self.assertEqual(by_name.get('Id'), 'ABC123')
        self.assertEqual(by_name.get('Circle'), 'Assam')
