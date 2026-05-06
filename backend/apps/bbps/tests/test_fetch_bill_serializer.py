from django.test import SimpleTestCase

from apps.bbps.serializers import FetchBillSerializer


class FetchBillSerializerTests(SimpleTestCase):
    def test_accepts_blank_top_level_customer_number_with_input_params(self):
        """Values may live only in input_params; empty customer_number must not fail validation."""
        s = FetchBillSerializer(
            data={
                'biller_id': 'DUMMY0000DIG05',
                'customer_number': '',
                'input_params': [{'paramName': 'CustomerId', 'paramValue': 'h696077'}],
            }
        )
        self.assertTrue(s.is_valid(), msg=str(s.errors))

    def test_accepts_blank_mobile(self):
        s = FetchBillSerializer(
            data={
                'biller_id': 'DUMMY0000DIG05',
                'mobile': '',
                'input_params': [{'paramName': 'CustomerId', 'paramValue': 'h696077'}],
            }
        )
        self.assertTrue(s.is_valid(), msg=str(s.errors))
