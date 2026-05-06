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
