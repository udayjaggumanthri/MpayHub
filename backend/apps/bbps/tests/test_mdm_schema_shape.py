from django.test import TestCase

from apps.bbps.models import (
    BbpsBillerAdditionalInfoSchema,
    BbpsBillerInputParam,
    BbpsBillerMaster,
    BbpsBillerPlanMeta,
)
from apps.bbps.services import (
    get_biller_additional_info_schema,
    get_biller_input_schema,
    get_biller_plans_lite,
    normalize_schema_choices,
)


class MdmSchemaShapeTests(TestCase):
    def setUp(self):
        self.master = BbpsBillerMaster.objects.create(
            biller_id='SCHEMA01',
            biller_name='Schema Test',
            biller_category='DTH',
            biller_status='ACTIVE',
            plan_mdm_requirement='MANDATORY',
            is_active_local=True,
        )

    def test_input_schema_includes_choices_and_input_kind(self):
        BbpsBillerInputParam.objects.create(
            biller=self.master,
            param_name='Region',
            data_type='ALPHANUMERIC',
            is_optional=True,
            min_length=0,
            max_length=10,
            regex='',
            visibility=True,
            display_order=1,
            default_values=[{'value': 'A', 'label': 'Alpha'}, {'value': 'B', 'label': 'Beta'}],
            mdm_extras={'help_text': 'Pick one'},
        )
        rows = get_biller_input_schema('SCHEMA01')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['input_kind'], 'select')
        self.assertEqual(len(rows[0]['choices']), 2)
        self.assertEqual(rows[0]['help_text'], 'Pick one')
        self.assertIn('constraints_hint', rows[0])
        self.assertIn('billavenue_param_key', rows[0])

    def test_input_schema_display_label_from_mdm_extras(self):
        BbpsBillerInputParam.objects.create(
            biller=self.master,
            param_name='a',
            data_type='ALPHANUMERIC',
            is_optional=False,
            min_length=1,
            max_length=20,
            regex='',
            visibility=True,
            display_order=1,
            default_values=[],
            mdm_extras={'display_label': 'Customer mobile number'},
        )
        rows = get_biller_input_schema('SCHEMA01')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['param_name'], 'a')
        self.assertEqual(rows[0]['display_label'], 'Customer mobile number')
        self.assertEqual(rows[0]['label'], 'Customer mobile number')

    def test_input_schema_display_label_from_raw_payload_when_extras_empty(self):
        self.master.raw_payload = {
            'billerId': 'SCHEMA01',
            'billerInputParams': {
                'paramsList': [{'paramName': 'a', 'paramLabel': 'Subscriber ID from bill', 'dataType': 'ALPHANUMERIC'}]
            },
        }
        self.master.save(update_fields=['raw_payload'])
        BbpsBillerInputParam.objects.create(
            biller=self.master,
            param_name='a',
            data_type='ALPHANUMERIC',
            is_optional=False,
            min_length=1,
            max_length=20,
            regex='',
            visibility=True,
            display_order=1,
            default_values=[],
            mdm_extras={},
        )
        rows = get_biller_input_schema('SCHEMA01')
        self.assertEqual(rows[0]['display_label'], 'Subscriber ID from bill')

    def test_normalize_schema_choices_plain_strings(self):
        out = normalize_schema_choices(['x', 'y'])
        self.assertEqual(out, [{'value': 'x', 'label': 'x'}, {'value': 'y', 'label': 'y'}])

    def test_additional_info_grouped(self):
        BbpsBillerAdditionalInfoSchema.objects.create(
            biller=self.master,
            info_group='billerAdditionalInfoPayment',
            info_name='PAN',
            data_type='ALPHANUMERIC',
            is_optional=True,
        )
        grouped = get_biller_additional_info_schema('SCHEMA01')
        self.assertIn('billerAdditionalInfoPayment', grouped)
        self.assertEqual(grouped['billerAdditionalInfoPayment'][0]['info_name'], 'PAN')

    def test_plans_lite_truncation_flag(self):
        for i in range(5):
            BbpsBillerPlanMeta.objects.create(
                biller=self.master,
                plan_id=f'P{i}',
                plan_desc=f'Plan {i}',
                amount_in_rupees='10',
                status='ACTIVE',
            )
        rows, truncated = get_biller_plans_lite('SCHEMA01', limit=3)
        self.assertEqual(len(rows), 3)
        self.assertTrue(truncated)

    def test_input_schema_enriches_csv_values_from_raw_and_hides_invisible(self):
        self.master.raw_payload = {
            'billerId': 'SCHEMA01',
            'billerInputParams': {
                'paramInfo': [
                    {
                        'paramName': 'Circle',
                        'values': 'Andhra Pradesh,Assam,Bihar',
                        'dataType': 'ALPHANUMERIC',
                        'visibility': 'true',
                        'isOptional': 'false',
                    },
                    {
                        'paramName': 'Id',
                        'regEx': '^[A-Z0-9]{2,4}[A-Za-z]{5,8}$',
                        'dataType': 'ALPHANUMERIC',
                        'visibility': 'false',
                        'isOptional': 'false',
                    },
                    {
                        'paramName': 'Mobile Number',
                        'dataType': 'NUMERIC',
                        'visibility': 'true',
                        'isOptional': 'false',
                    },
                ]
            },
        }
        self.master.save(update_fields=['raw_payload'])
        BbpsBillerInputParam.objects.create(
            biller=self.master,
            param_name='Circle',
            data_type='ALPHANUMERIC',
            is_optional=False,
            visibility=True,
            display_order=1,
            default_values=[],
        )
        BbpsBillerInputParam.objects.create(
            biller=self.master,
            param_name='Id',
            data_type='ALPHANUMERIC',
            is_optional=False,
            visibility=False,
            display_order=2,
            default_values=[],
            regex='^[A-Z0-9]{2,4}[A-Za-z]{5,8}$',
        )
        BbpsBillerInputParam.objects.create(
            biller=self.master,
            param_name='Mobile Number',
            data_type='NUMERIC',
            is_optional=False,
            visibility=True,
            display_order=3,
            default_values=[],
        )
        rows = get_biller_input_schema('SCHEMA01')
        names = [r['param_name'] for r in rows]
        # Required + visibility=false (Id) must still appear for agent entry.
        self.assertEqual(names, ['Circle', 'Id', 'Mobile Number'])
        circle = rows[0]
        self.assertEqual(circle['input_kind'], 'select')
        self.assertEqual([c['value'] for c in circle['choices']], ['Andhra Pradesh', 'Assam', 'Bihar'])
        self.assertFalse(rows[1]['visibility'])
        self.assertFalse(rows[1]['is_optional'])
