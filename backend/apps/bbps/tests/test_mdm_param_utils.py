import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.bbps.mdm_param_utils import extract_param_lov_and_extras, infer_input_kind, normalize_schema_choices


class MdmParamUtilsTests(SimpleTestCase):
    def test_extract_lov_from_list_of_values(self):
        row = {
            'paramName': 'Region',
            'listOfValues': [{'value': 'URBAN', 'displayName': 'Urban'}, {'value': 'RURAL', 'displayName': 'Rural'}],
        }
        choices, extras = extract_param_lov_and_extras(row)
        self.assertEqual(len(choices), 2)
        self.assertEqual(choices[0]['value'], 'URBAN')
        self.assertEqual(choices[1]['label'], 'Rural')
        self.assertIn('lov_source_key', extras)

    def test_extract_help_text(self):
        row = {'paramName': 'X', 'paramHelpText': 'Enter value from bill'}
        _, extras = extract_param_lov_and_extras(row)
        self.assertEqual(extras.get('help_text'), 'Enter value from bill')

    def test_infer_input_kind(self):
        self.assertEqual(infer_input_kind(data_type='ALPHANUMERIC', choices=[]), 'text')
        self.assertEqual(infer_input_kind(data_type='NUMERIC', choices=[]), 'numeric')
        self.assertEqual(infer_input_kind(data_type='DATE', choices=[]), 'date')
        self.assertEqual(infer_input_kind(data_type='TEXT', choices=[{'value': 'a', 'label': 'A'}]), 'select')

    def test_fixture_profiles_parseable(self):
        path = Path(__file__).resolve().parent / 'fixtures' / 'mdm_biller_profiles.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        for key in ('simple_dth', 'utility_with_lov', 'plan_mandatory_prepaid'):
            block = data[key]['billerInputParams']['paramsList'][0]
            choices, extras = extract_param_lov_and_extras(block)
            self.assertIsInstance(choices, list)
            self.assertIsInstance(extras, dict)
