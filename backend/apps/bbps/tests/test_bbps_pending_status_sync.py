"""Save-first BBPS pay, honest classification, and shared status sync."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.bbps.bill_payments_filters import apply_bill_payments_list_filters
from apps.bbps.models import BillPayment, BbpsBillerMaster, BbpsFetchSession, BbpsPaymentAttempt, BbpsStatusPollLog
from apps.bbps.service_flow.payment_service import process_bill_payment_flow
from apps.bbps.service_flow.recovery import admin_mark_bbps_failed, admin_mark_bbps_success
from apps.bbps.service_flow.status_service import due_pending_attempts, poll_attempt_status
from apps.bbps.service_flow.user_wallet_settlement import place_payment_hold, release_stale_bbps_holds
from apps.core.exceptions import InsufficientBalance, TransactionFailed
from apps.integrations.bbps_client import BBPSClient, classify_immediate_pay_reply
from apps.integrations.billavenue.errors import BillAvenueTransportError
from apps.transactions.models import PassbookEntry
from apps.wallets.models import Wallet


def _user(*, phone, email, role, user_id):
    return User.objects.create_user(
        phone=phone,
        email=email,
        password='TestPass123!',
        role=role,
        user_id=user_id,
        first_name='Test',
        last_name='User',
    )


class ClassifyImmediatePayTests(TestCase):
    def test_000_with_real_approval_without_explicit_success_stays_pending(self):
        out = classify_immediate_pay_reply(
            envelope_code='000',
            inner_code='000',
            txn_ref_id='CCUNIT0001',
            approval_ref_number='AB12345',
            reason='Accepted',
            payload={'responseCode': '000'},
        )
        self.assertEqual(out['status'], 'AWAITED')

    def test_successful_forward_type_response_is_success(self):
        out = classify_immediate_pay_reply(
            envelope_code='000',
            inner_code='000',
            txn_resp_type='FORWARD TYPE RESPONSE',
            txn_ref_id='CC016281BAAG00080744',
            approval_ref_number='AB123456',
            reason='Successful',
            payload={'responseReason': 'Successful', 'txnRespType': 'FORWARD TYPE RESPONSE'},
        )
        self.assertEqual(out['status'], 'SUCCESS')

    def test_explicit_success_is_success(self):
        out = classify_immediate_pay_reply(
            envelope_code='000',
            inner_code='000',
            txn_status='SUCCESS',
            txn_ref_id='CCUNIT0002',
            approval_ref_number='AB99999',
            payload={'txnStatus': 'SUCCESS'},
        )
        self.assertEqual(out['status'], 'SUCCESS')

    def test_forward_zero_approval_and_999_stay_pending(self):
        forward = classify_immediate_pay_reply(
            envelope_code='000',
            txn_resp_type='FORWARD',
            txn_ref_id='CCUNIT0003',
            approval_ref_number='AB1',
            payload={'txnRespType': 'FORWARD'},
        )
        zeros = classify_immediate_pay_reply(
            envelope_code='000',
            approval_ref_number='00000000',
            txn_ref_id='CCUNIT0004',
            payload={'approvalRefNumber': '00000000'},
        )
        in_process = classify_immediate_pay_reply(
            envelope_code='999',
            reason='PNR003 payment in process',
            approval_ref_number='00000000',
            txn_ref_id='CCUNIT0005',
            payload={'responseCode': '999'},
        )
        self.assertEqual(forward['status'], 'AWAITED')
        self.assertEqual(zeros['status'], 'AWAITED')
        self.assertEqual(in_process['status'], 'AWAITED')

    def test_clear_reject_without_txn_id_is_failed(self):
        out = classify_immediate_pay_reply(
            envelope_code='001',
            inner_code='001',
            reason='Invalid account',
            payload={'responseCode': '001'},
        )
        self.assertEqual(out['status'], 'FAILED')
        self.assertEqual(out['txn_ref_id'], '')

    def test_timeout_does_not_retry_bill_pay(self):
        client = BBPSClient()
        client.client = MagicMock()
        client.client.bill_pay.side_effect = BillAvenueTransportError('TIMEOUT')
        with patch.object(client, '_build_bill_payment_payload', return_value={'requestId': 'R'}):
            out = client.process_payment(
                'PMBBPSUNIT1',
                'REQ1',
                Decimal('10'),
                {'biller_id': 'B1', 'input_params': [], 'customer_info': {}, 'remitter_name': 'A'},
            )
        self.assertEqual(out['status'], 'AWAITED')
        self.assertEqual(client.client.bill_pay.call_count, 1)


@override_settings(BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED=True)
class SaveFirstPaymentFlowTests(TestCase):
    def setUp(self):
        self.user = _user(
            phone='9222000001',
            email='bbps.sync@example.com',
            role='Retailer',
            user_id='BBPSSYNC1',
        )
        self.wallet = Wallet.get_wallet(self.user, 'main')
        self.wallet.credit(Decimal('1000.0000'), reference='seed', description='seed')
        self.biller = BbpsBillerMaster.objects.create(
            environment='uat',
            biller_id='UNITBILLER01',
            biller_name='Unit Biller',
            biller_status='ACTIVE',
        )
        self.fetch = BbpsFetchSession.objects.create(
            user=self.user,
            biller_master=self.biller,
            request_id='REQFETCH1',
            status='FETCHED',
        )
        self.pay_calls = []

    def _bill(self, service_id):
        return {
            'amount': '100.00',
            'biller_id': self.biller.biller_id,
            'biller': 'Unit Biller',
            'bill_type': 'Electricity',
            'payment_mode': 'Cash',
            'init_channel': 'AGT',
            'agent_device_info': {'initChannel': 'AGT', 'ip': '127.0.0.1'},
            'input_params': [{'paramName': 'Mobile', 'paramValue': '9999999999'}],
            'customer_info': {'customerMobile': '9999999999', 'customerName': 'Test User'},
            'remitter_name': 'Test User',
            'service_id': service_id,
            'request_id': self.fetch.request_id,
        }

    def _patches(self, payment_result):
        client = MagicMock()

        def _pay(*args, **kwargs):
            self.pay_calls.append(1)
            self.assertTrue(BillPayment.objects.filter(service_id=args[0]).exists())
            row = BillPayment.objects.get(service_id=args[0])
            self.assertEqual(row.status, 'PENDING')
            self.wallet.refresh_from_db()
            self.assertGreater(self.wallet.held_balance, 0)
            if isinstance(payment_result, Exception):
                raise payment_result
            return payment_result

        client.process_payment.side_effect = _pay
        client._build_bill_payment_payload.return_value = {}
        return [
            patch('apps.bbps.service_flow.payment_service.get_biller_master', return_value=self.biller),
            patch('apps.bbps.service_flow.payment_service.validate_channel_device_fields'),
            patch('apps.bbps.service_flow.payment_service.enforce_biller_mode_channel_constraints'),
            patch('apps.bbps.service_flow.payment_service.enforce_plan_mdm_requirement'),
            patch('apps.bbps.service_flow.payment_service.enforce_fetch_pay_linkage', return_value=self.fetch),
            patch('apps.bbps.service_flow.payment_service.enforce_payment_amount_policy'),
            patch('apps.bbps.service_flow.payment_service.enforce_cash_pan_rule'),
            patch(
                'apps.bbps.service_flow.payment_service.resolve_commission_for_payment',
                return_value={
                    'charge': Decimal('0'),
                    'computed_charge': Decimal('0'),
                    'commission_rule_code': '',
                    'commission_rule_snapshot': {},
                },
            ),
            patch('apps.bbps.service_flow.payment_service.assert_float_available'),
            patch('apps.bbps.notifications.notify_payment_attempt_status'),
            patch('apps.bbps.service_flow.payment_service.BBPSClient', return_value=client),
        ]

    def _run(self, service_id, payment_result):
        patches = self._patches(payment_result)
        for item in patches:
            item.start()
        try:
            return process_bill_payment_flow(user=self.user, bill_data=self._bill(service_id))
        finally:
            for item in patches:
                item.stop()

    def test_timeout_keeps_pending_hold_and_row(self):
        before = self.wallet.available_balance
        result = self._run(
            'PMBBPSUNITA1',
            {'status': 'AWAITED', 'message': 'timeout', 'txn_ref_id': '', 'response_payload': {'timeout': True}},
        )
        self.fetch.refresh_from_db()
        self.wallet.refresh_from_db()
        bill = result['bill_payment']
        bill.refresh_from_db()
        self.assertEqual(bill.status, 'PENDING')
        self.assertEqual(result['attempt'].status, 'AWAITED')
        self.assertEqual(self.fetch.status, 'CONSUMED')
        self.assertEqual(self.wallet.available_balance, before - bill.total_deducted)
        self.assertTrue(BillPayment.objects.filter(pk=bill.pk).exists())

    def test_clear_reject_returns_failed_and_keeps_fetch(self):
        result = self._run(
            'PMBBPSUNITA2',
            {'status': 'FAILED', 'message': 'Invalid account', 'txn_ref_id': '', 'response_payload': {'responseCode': '001'}},
        )
        self.fetch.refresh_from_db()
        self.wallet.refresh_from_db()
        bill = result['bill_payment']
        bill.refresh_from_db()
        self.assertEqual(bill.status, 'FAILED')
        self.assertEqual(self.fetch.status, 'FETCHED')
        self.assertEqual(self.wallet.held_balance, Decimal('0'))
        self.assertTrue(BillPayment.objects.filter(pk=bill.pk, status='FAILED').exists())

    def test_in_flight_fetch_does_not_call_bill_pay_again(self):
        self._run(
            'PMBBPSUNITA3',
            {'status': 'AWAITED', 'message': 'pending', 'txn_ref_id': 'CCUNITFLOW1', 'response_payload': {}},
        )
        calls = len(self.pay_calls)
        again = self._run(
            'PMBBPSUNITA4',
            {'status': 'AWAITED', 'message': 'should not run', 'txn_ref_id': '', 'response_payload': {}},
        )
        self.assertTrue(again['idempotent'])
        self.assertEqual(len(self.pay_calls), calls)
        self.assertEqual(again['bill_payment'].service_id, 'PMBBPSUNITA3')

    def test_failed_without_txn_allows_a_new_attempt(self):
        self._run(
            'PMBBPSUNITA5',
            {'status': 'FAILED', 'message': 'Invalid account', 'txn_ref_id': '', 'response_payload': {}},
        )
        self.fetch.refresh_from_db()
        self.assertEqual(self.fetch.status, 'FETCHED')
        second = self._run(
            'PMBBPSUNITA6',
            {'status': 'AWAITED', 'message': 'retry', 'txn_ref_id': '', 'response_payload': {}},
        )
        self.assertFalse(second['idempotent'])
        self.assertEqual(second['bill_payment'].service_id, 'PMBBPSUNITA6')
        self.assertEqual(BbpsPaymentAttempt.objects.filter(user=self.user).count(), 2)

    def test_insufficient_balance_creates_no_row(self):
        self.wallet.balance = Decimal('1.0000')
        self.wallet.held_balance = Decimal('0')
        self.wallet.save(update_fields=['balance', 'held_balance'])
        with self.assertRaises(InsufficientBalance):
            self._run(
                'PMBBPSUNITA7',
                {'status': 'AWAITED', 'message': 'nope', 'txn_ref_id': '', 'response_payload': {}},
            )
        self.assertFalse(BillPayment.objects.filter(service_id='PMBBPSUNITA7').exists())


class StatusSyncAndRecoveryTests(TestCase):
    def setUp(self):
        self.user = _user(
            phone='9222000002',
            email='bbps.sync2@example.com',
            role='Retailer',
            user_id='BBPSSYNC2',
        )
        self.other = _user(
            phone='9222000003',
            email='bbps.sync3@example.com',
            role='Retailer',
            user_id='BBPSSYNC3',
        )
        self.admin = _user(
            phone='9222000004',
            email='bbps.admin@example.com',
            role='Admin',
            user_id='BBPSADM01',
        )
        self.wallet = Wallet.get_wallet(self.user, 'main')
        self.wallet.credit(Decimal('1000.0000'), reference='seed', description='seed')

    def _pending(self, service_id, *, txn_ref='', status='AWAITED'):
        bill = BillPayment.objects.create(
            user=self.user,
            biller='Unit',
            biller_id='UNITBILLER01',
            bill_type='fastag',
            amount=Decimal('50.0000'),
            charge=Decimal('0'),
            total_deducted=Decimal('50.0000'),
            status='PENDING',
            service_id=service_id,
            request_id=f'R{service_id}',
        )
        attempt = BbpsPaymentAttempt.objects.create(
            user=self.user,
            bill_payment=bill,
            idempotency_key=f'idem-{service_id}',
            request_id=bill.request_id,
            service_id=service_id,
            biller_id='UNITBILLER01',
            amount_paise=5000,
            status=status,
            txn_ref_id=txn_ref,
        )
        place_payment_hold(attempt=attempt, amount=bill.total_deducted)
        return attempt

    def test_sweeper_does_not_fail_in_flight_without_bconnect_id(self):
        attempt = self._pending('PMBBPSSWEEP1', txn_ref='')
        BbpsPaymentAttempt.objects.filter(pk=attempt.pk).update(
            created_at=timezone.now() - timedelta(hours=72)
        )
        released = release_stale_bbps_holds(older_than_hours=48)
        attempt.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(released, 0)
        self.assertEqual(attempt.status, 'AWAITED')
        self.assertEqual(attempt.bill_payment.status, 'PENDING')
        self.assertGreater(attempt.wallet_hold_amount, 0)
        self.assertGreater(self.wallet.held_balance, 0)

    def test_status_sync_success_settles_once_and_cooling_skips_provider(self):
        attempt = self._pending('PMBBPSSYNC1', txn_ref='CCUNITSYNC1')
        client = MagicMock()
        client.transaction_status.return_value = {'txnStatus': 'SUCCESS', 'responseCode': '000'}
        with patch('apps.bbps.service_flow.status_service.BBPSClient', return_value=client), patch(
            'apps.bbps.notifications.notify_payment_attempt_status'
        ):
            first = poll_attempt_status(attempt, requested_by=self.user, source='user')
            second = poll_attempt_status(first.attempt, requested_by=self.user, source='user')
        self.assertTrue(first.status_changed)
        self.assertEqual(first.attempt.status, 'SUCCESS')
        self.assertEqual(PassbookEntry.objects.filter(service_id='PMBBPSSYNC1', service='BBPS').count(), 1)
        self.assertFalse(second.status_changed)
        self.assertEqual(PassbookEntry.objects.filter(service_id='PMBBPSSYNC1', service='BBPS').count(), 1)
        log = BbpsStatusPollLog.objects.get(attempt=attempt, status_changed=True)
        self.assertEqual(log.source, 'user')
        self.assertEqual(log.requested_by_id, self.user.pk)
        self.assertTrue(log.status_changed)

    def test_status_sync_failure_releases_once(self):
        attempt = self._pending('PMBBPSSYNC2', txn_ref='CCUNITSYNC2')
        client = MagicMock()
        client.transaction_status.return_value = {'txnStatus': 'FAILURE', 'responseCode': '001'}
        with patch('apps.bbps.service_flow.status_service.BBPSClient', return_value=client), patch(
            'apps.bbps.notifications.notify_payment_attempt_status'
        ):
            result = poll_attempt_status(attempt, source='job')
        attempt.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(result.attempt.status, 'FAILED')
        self.assertEqual(attempt.bill_payment.status, 'FAILED')
        self.assertEqual(self.wallet.held_balance, Decimal('0'))

    def test_unclear_status_leaves_pending(self):
        attempt = self._pending('PMBBPSSYNC3', txn_ref='CCUNITSYNC3')
        client = MagicMock()
        client.transaction_status.return_value = {}
        with patch('apps.bbps.service_flow.status_service.BBPSClient', return_value=client):
            result = poll_attempt_status(attempt, source='job')
            cooled = poll_attempt_status(result.attempt, source='job')
        attempt.refresh_from_db()
        self.assertFalse(result.status_changed)
        self.assertEqual(attempt.status, 'AWAITED')
        self.assertEqual(attempt.bill_payment.status, 'PENDING')
        self.assertGreater(attempt.wallet_hold_amount, 0)
        self.assertTrue(cooled.cooling_active)
        self.assertEqual(client.transaction_status.call_count, 1)

    def test_job_selects_only_due_rows(self):
        due = self._pending('PMBBPSDUE1', txn_ref='CCUNITDUE1')
        recent = self._pending('PMBBPSDUE2', txn_ref='CCUNITDUE2')
        BbpsPaymentAttempt.objects.filter(pk=recent.pk).update(last_status_checked_at=timezone.now())
        ids = list(due_pending_attempts(minimum_minutes=15, limit=20).values_list('service_id', flat=True))
        self.assertIn(due.service_id, ids)
        self.assertNotIn(recent.service_id, ids)

    def test_admin_mark_success_and_failed_are_idempotent(self):
        ok = self._pending('PMBBPSMARK1', txn_ref='CCUNITMARK1')
        admin_mark_bbps_success(attempt=ok, actor=self.admin, internal_note='confirmed')
        admin_mark_bbps_success(attempt=ok, actor=self.admin, internal_note='again')
        self.assertEqual(PassbookEntry.objects.filter(service_id='PMBBPSMARK1', service='BBPS').count(), 1)

        bad = self._pending('PMBBPSMARK2', txn_ref='')
        admin_mark_bbps_failed(attempt=bad, actor=self.admin, reason='not paid', internal_note='ops')
        admin_mark_bbps_failed(attempt=bad, actor=self.admin, reason='not paid', internal_note='ops')
        bad.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(bad.status, 'FAILED')
        self.assertEqual(bad.wallet_hold_amount, Decimal('0'))
        self.assertEqual(self.wallet.held_balance, Decimal('0'))

    def test_admin_complaint_targets_another_retailer(self):
        attempt = self._pending('PMBBPSCMP1', txn_ref='CCUNITCMP01', status='SUCCESS')
        attempt.bill_payment.status = 'SUCCESS'
        attempt.bill_payment.save(update_fields=['status'])
        attempt.settled_at = timezone.now()
        attempt.wallet_hold_amount = Decimal('0')
        attempt.wallet_settled_amount = Decimal('50.0000')
        attempt.save(update_fields=['settled_at', 'wallet_hold_amount', 'wallet_settled_amount'])
        with self.assertRaises(TransactionFailed):
            from apps.bbps.service_flow.complaint_service import register_complaint

            register_complaint(
                user=self.other,
                txn_ref_id='CCUNITCMP01',
                complaint_desc='Amount debited but service not received',
                complaint_disposition='Transaction Successful, Amount Debited but services not received',
            )
        client = MagicMock()
        client.transaction_status.return_value = {'txnList': [{'txnRefId': 'CCUNITCMP01', 'txnStatus': 'SUCCESS'}]}
        client.register_complaint.return_value = (
            {'complaintId': 'CMP1', 'complaintStatus': 'ASSIGNED', 'responseCode': '000'},
            'BAREQ1',
        )
        api = APIClient()
        api.force_authenticate(self.admin)
        with patch('apps.bbps.service_flow.complaint_service.BBPSClient', return_value=client), patch(
            'apps.bbps.notifications.notify_complaint_registered'
        ):
            res = api.post(
                f'/api/admin/bbps-recovery/{attempt.pk}/complaint/',
                {
                    'complaint_desc': 'Amount debited but service not received',
                    'complaint_disposition': 'Transaction Successful, Amount Debited but services not received',
                },
                format='json',
            )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['data']['user_id'], self.user.pk)

    def test_reports_search_finds_bconnect_id(self):
        attempt = self._pending('PMBBPSRPT1', txn_ref='CCUNITREPORT1')
        request = MagicMock()
        request.query_params = {'search': 'CCUNITREPORT1'}
        qs = apply_bill_payments_list_filters(BillPayment.objects.filter(pk=attempt.bill_payment_id), request)
        self.assertEqual(list(qs.values_list('service_id', flat=True)), ['PMBBPSRPT1'])
