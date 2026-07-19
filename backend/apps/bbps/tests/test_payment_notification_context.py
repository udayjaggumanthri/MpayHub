from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.authentication.models import User
from apps.bbps.models import BillPayment, BbpsBillerMaster, BbpsPaymentAttempt, BbpsServiceCategory
from apps.bbps.notifications import notify_payment_attempt_status
from apps.bbps.payment_notification_context import (
    build_payment_notification_context,
    resolve_consumer_id,
    resolve_user_display_name,
    status_display,
)
from apps.users.models import UserProfile


class PaymentNotificationContextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9222222222',
            email='notify@test.com',
            password='secret123',
            role='Retailer',
            user_id='NOTIFY1',
        )
        UserProfile.objects.create(
            user=self.user,
            first_name='Tarun',
            last_name='Iyer',
            business_name='Test Business',
        )
        BbpsServiceCategory.objects.create(
            code='mobile-postpaid',
            name='Mobile Postpaid',
            is_active=True,
        )
        BbpsBillerMaster.objects.create(
            biller_id='DUMMYFASTAG001',
            biller_name='Bank of Baroda FASTag',
            biller_category='FASTag',
            biller_status='ACTIVE',
        )

    def _create_attempt(self, *, bill_type, payload, status='SUCCESS', txn_ref_id='CC1234567890123456789012345678901234', suffix=''):
        service_id = f'PMBBPS{bill_type}-{suffix or status}'
        payment = BillPayment.objects.create(
            user=self.user,
            biller='Test Biller',
            biller_id='BILLER001',
            bill_type=bill_type,
            amount=Decimal('250'),
            charge=Decimal('5'),
            total_deducted=Decimal('255'),
            status=status,
            service_id=service_id,
            request_id='REQ001',
        )
        return BbpsPaymentAttempt.objects.create(
            user=self.user,
            bill_payment=payment,
            idempotency_key=f'idem-{service_id}',
            service_id=payment.service_id,
            biller_id='BILLER001',
            amount_paise=25000,
            status=status,
            txn_ref_id=txn_ref_id,
            request_payload=payload,
        )

    def test_resolve_user_display_name_from_profile(self):
        self.assertEqual(resolve_user_display_name(self.user), 'Tarun Iyer')

    def test_fastag_consumer_id_from_vehicle_param(self):
        attempt = self._create_attempt(
            bill_type='fastag',
            suffix='fastag',
            payload={
                'input_params': [{'paramName': 'Vehicle Number', 'paramValue': 'MH15AT6555'}],
            },
        )
        self.assertEqual(resolve_consumer_id(attempt), 'MH15AT6555')

    def test_mobile_postpaid_consumer_id(self):
        attempt = self._create_attempt(
            bill_type='mobile-postpaid',
            suffix='mobile',
            payload={
                'input_params': [{'paramName': 'Mobile Number', 'paramValue': '9876543210'}],
            },
        )
        ctx = build_payment_notification_context(attempt, 'SUCCESS')
        self.assertEqual(ctx['consumer_id'], '9876543210')
        self.assertEqual(ctx['service'], 'Mobile Postpaid')
        self.assertEqual(ctx['name'], 'Tarun Iyer')
        self.assertEqual(ctx['b_connect_txn_id'], 'CC1234567890123456789012345678901234')
        self.assertEqual(ctx['txn_ref'], ctx['b_connect_txn_id'])
        self.assertEqual(ctx['receipt_no'], ctx['b_connect_txn_id'])
        self.assertEqual(ctx['status'], 'Success')

    def test_failed_status_context(self):
        attempt = self._create_attempt(
            bill_type='electricity',
            suffix='failed',
            payload={'input_params': [{'paramName': 'Consumer Number', 'paramValue': 'CONS123'}]},
            status='FAILED',
            txn_ref_id='',
        )
        attempt.last_error_message = 'Declined by biller'
        attempt.save(update_fields=['last_error_message'])
        ctx = build_payment_notification_context(attempt, 'FAILED')
        self.assertEqual(ctx['status'], 'Failed')
        self.assertEqual(ctx['reason'], 'Declined by biller')
        self.assertEqual(ctx['consumer_id'], 'CONS123')
        self.assertNotIn('txn_ref', ctx)

    def test_awaited_status_display_pending(self):
        attempt = self._create_attempt(
            bill_type='mobile-postpaid',
            suffix='awaited',
            payload={'mobile': '9876543210'},
            status='AWAITED',
        )
        ctx = build_payment_notification_context(attempt, 'AWAITED')
        self.assertEqual(ctx['status'], 'Pending')
        self.assertEqual(status_display('AWAITED'), 'Pending')

    @patch('apps.notifications.services.email_dispatch.EmailNotificationService.dispatch')
    @patch('apps.notifications.services.dispatch.SmsNotificationService.dispatch')
    def test_notify_payment_attempt_status_passes_new_context_keys(
        self, mock_sms_dispatch, mock_email_dispatch
    ):
        attempt = self._create_attempt(
            bill_type='mobile-postpaid',
            suffix='notify',
            payload={'mobile': '9876543210'},
            status='SUCCESS',
        )
        notify_payment_attempt_status(attempt)
        mock_email_dispatch.assert_called_once()
        _event, _email, context = mock_email_dispatch.call_args[0]
        self.assertEqual(context['name'], 'Tarun Iyer')
        self.assertEqual(context['service'], 'Mobile Postpaid')
        self.assertEqual(context['consumer_id'], '9876543210')
        self.assertEqual(context['status'], 'Success')
        self.assertIn('b_connect_txn_id', context)
