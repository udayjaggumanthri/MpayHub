"""Query budget for BBPS bill payments list (no per-row attempt N+1)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.bbps.models import BillPayment, BbpsPaymentAttempt

User = get_user_model()


class BillPaymentsListQueryBudgetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9100000099',
            email='bp-list-budget@test.com',
            password='testpass123',
            role='Retailer',
            user_id='BPLB1',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _payment(self, idx: int) -> BillPayment:
        bp = BillPayment.objects.create(
            user=self.user,
            biller=f'Biller {idx}',
            biller_id=f'BID{idx:04d}',
            bill_type='credit-card',
            amount=Decimal('100'),
            charge=Decimal('1'),
            total_deducted=Decimal('101'),
            status='SUCCESS',
            service_id=f'BP-LIST-{idx:04d}',
            request_id=f'req-{idx}',
        )
        BbpsPaymentAttempt.objects.create(
            user=self.user,
            bill_payment=bp,
            idempotency_key=f'idem-{idx}',
            txn_ref_id=f'TXN{idx}',
            approval_ref_number=f'APR{idx}',
            request_payload={
                'input_params': [{'paramName': 'Mobile Number', 'paramValue': '9876543210'}],
                'customer_details': {'mobile': '9876543210'},
            },
        )
        return bp

    def test_list_query_count_stable_with_more_payments(self):
        for i in range(5):
            self._payment(i)
        with CaptureQueriesContext(connection) as ctx5:
            r5 = self.client.get('/api/bbps/payments/', {'scope': 'self', 'page_size': 25})
        self.assertEqual(r5.status_code, 200)
        n5 = len(ctx5.captured_queries)

        for i in range(5, 25):
            self._payment(i)
        with CaptureQueriesContext(connection) as ctx25:
            r25 = self.client.get('/api/bbps/payments/', {'scope': 'self', 'page_size': 25})
        self.assertEqual(r25.status_code, 200)
        n25 = len(ctx25.captured_queries)
        self.assertGreaterEqual(len(r25.data['data']['payments']), 20)
        self.assertLessEqual(n25, n5 + 2, f'n5={n5} n25={n25}')
        self.assertLessEqual(n25, 25)
