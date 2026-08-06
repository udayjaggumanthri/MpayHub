import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.bbps.catalog.mdm_parse import extract_param_rows
from apps.bbps.mdm_param_utils import (
    constraints_hint_for_schema_row,
    extract_param_lov_and_extras,
    infer_input_kind,
    input_schema_display_label,
    is_placeholder_style_param_name,
    normalize_schema_choices,
)


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

    def test_extract_display_label_from_param_label(self):
        row = {'paramName': 'a', 'paramLabel': 'Subscriber number'}
        _, extras = extract_param_lov_and_extras(row)
        self.assertEqual(extras.get('display_label'), 'Subscriber number')

    def test_is_placeholder_style_param_name(self):
        self.assertTrue(is_placeholder_style_param_name('a'))
        self.assertTrue(is_placeholder_style_param_name('a b c'))
        self.assertFalse(is_placeholder_style_param_name('CustomerId'))
        self.assertFalse(is_placeholder_style_param_name('Mobile Number'))

    def test_input_schema_display_label_fallback_for_placeholder_wire(self):
        lab = input_schema_display_label(
            wire='a b',
            help_text='',
            extras={},
            order=2,
            raw_row=None,
        )
        self.assertEqual(lab, 'Bill reference detail 2')

    def test_extract_param_rows_skips_empty_params_list_wrapper(self):
        outer = {'paramsList': [], 'note': 'x'}
        self.assertEqual(extract_param_rows([outer]), [])

    def test_extract_param_rows_accepts_direct_param_dicts(self):
        rows = extract_param_rows([{'paramName': 'CustomerId', 'dataType': 'ALPHANUMERIC', 'minLength': 3}])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['paramName'], 'CustomerId')

    def test_constraints_hint_for_schema_row(self):
        h = constraints_hint_for_schema_row(
            min_length=10,
            max_length=10,
            data_type='NUMERIC',
            regex='',
            input_kind='numeric',
        )
        self.assertIn('10', h)
        self.assertIn('characters', h)
        self.assertIn('NUMERIC', h)
        self.assertIn('digits only', h)

    def test_fixture_profiles_parseable(self):
        path = Path(__file__).resolve().parent / 'fixtures' / 'mdm_biller_profiles.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        for key in ('simple_dth', 'utility_with_lov', 'plan_mandatory_prepaid'):
            block = data[key]['billerInputParams']['paramsList'][0]
            choices, extras = extract_param_lov_and_extras(block)
            self.assertIsInstance(choices, list)
            self.assertIsInstance(extras, dict)

    def test_extract_lov_from_comma_separated_values(self):
        row = {
            'paramName': 'Circle',
            'values': 'Andhra Pradesh,Assam,Bihar,Chennai',
            'dataType': 'ALPHANUMERIC',
        }
        choices, extras = extract_param_lov_and_extras(row)
        self.assertEqual(len(choices), 4)
        self.assertEqual(choices[0]['value'], 'Andhra Pradesh')
        self.assertEqual(choices[3]['label'], 'Chennai')
        self.assertEqual(extras.get('lov_source_key'), 'values')
        self.assertEqual(infer_input_kind(data_type='ALPHANUMERIC', choices=choices), 'select')

    def test_extract_lov_from_regex_alternation_fallback(self):
        row = {
            'paramName': 'Circle',
            'regEx': '^(Andhra Pradesh)$|^(Assam)$|^(Bihar)$',
            'dataType': 'ALPHANUMERIC',
        }
        choices, extras = extract_param_lov_and_extras(row)
        self.assertEqual([c['value'] for c in choices], ['Andhra Pradesh', 'Assam', 'Bihar'])
        self.assertEqual(extras.get('lov_source_key'), 'regEx')

    def test_regex_character_class_not_treated_as_lov(self):
        row = {
            'paramName': 'Id',
            'regEx': '^[A-Z0-9]{2,4}[A-Za-z]{5,8}[0-9]{1,4}$',
            'dataType': 'ALPHANUMERIC',
        }
        choices, _ = extract_param_lov_and_extras(row)
        self.assertEqual(choices, [])
        self.assertEqual(infer_input_kind(data_type='ALPHANUMERIC', choices=choices), 'text')
