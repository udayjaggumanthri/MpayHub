from decimal import Decimal

from django.test import TestCase

from apps.authentication.models import User
from apps.bbps.models import BillPayment, BbpsBillerMaster, BbpsPaymentAttempt
from apps.bbps.receipt_context import build_bill_payment_receipt_context
from apps.bbps.serializers import BillPaymentSerializer


class BbpsReceiptContextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9111111111',
            email='receipt@test.com',
            password='secret123',
            role='Distributor',
        )
        BbpsBillerMaster.objects.create(
            biller_id='DUMMYFASTAG001',
            biller_name='Bank of Baroda FASTag',
            biller_category='FASTag',
            biller_status='ACTIVE',
        )
        self.payment = BillPayment.objects.create(
            user=self.user,
            biller='DUMMYFASTAG001',
            biller_id='DUMMYFASTAG001',
            bill_type='fastag',
            amount=Decimal('500'),
            charge=Decimal('5'),
            total_deducted=Decimal('505'),
            status='SUCCESS',
            service_id='PMBBPSTEST001',
            request_id='REQTEST001',
        )
        BbpsPaymentAttempt.objects.create(
            user=self.user,
            bill_payment=self.payment,
            idempotency_key='idem-receipt-1',
            service_id=self.payment.service_id,
            biller_id='DUMMYFASTAG001',
            amount_paise=50000,
            payment_mode='Cash',
            payment_channel='AGT',
            status='SUCCESS',
            request_payload={
                'payment_mode': 'Cash',
                'init_channel': 'AGT',
                'customer_name': 'VENAKATESH',
                'remitter_name': 'Tarun I',
                'input_params': [
                    {'paramName': 'Vehicle Number', 'paramValue': 'MH15AT6555'},
                ],
                'biller_response': {
                    'billFetchResponse': {
                        'billerResponse': {
                            'customerName': 'VENAKATESH',
                            'billDate': '20251107',
                            'dueDate': '20251107',
                            'billNumber': 'MH15AT6555',
                        }
                    }
                },
            },
        )

    def test_receipt_context_resolves_biller_name_and_payment_fields(self):
        ctx = build_bill_payment_receipt_context(self.payment)
        self.assertEqual(ctx['biller_name'], 'Bank of Baroda FASTag')
        self.assertEqual(ctx['payment_mode'], 'Cash')
        self.assertEqual(ctx['init_channel'], 'AGT')
        self.assertEqual(ctx['customer_name'], 'VENAKATESH')
        self.assertEqual(ctx['bill_number'], 'MH15AT6555')

    def test_serializer_exposes_receipt_details(self):
        data = BillPaymentSerializer(self.payment).data
        self.assertEqual(data['biller_name'], 'Bank of Baroda FASTag')
        self.assertEqual(data['payment_mode'], 'Cash')
        self.assertEqual(data['init_channel'], 'AGT')
        self.assertIn('receipt_details', data)
        self.assertEqual(data['receipt_details']['customer_name'], 'VENAKATESH')
