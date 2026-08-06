"""Deposit enquiry service + history API tests."""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.bbps.models import BbpsDepositEnquirySnapshot
from apps.bbps.service_flow.deposit_service import extract_deposit_transactions, enquire_deposits
from apps.integrations.billavenue.registry import activate_billavenue_config, get_or_create_billavenue_mode_row
from apps.integrations.models import BillAvenueAgentProfile


class DepositTxnParseTests(TestCase):
    def test_extract_transactions(self):
        rows = extract_deposit_transactions(
            {
                'currentBalance': '9999.00',
                'currency': 'INR',
                'responseCode': '000',
                'transaction': [
                    {
                        'amount': 9999.0,
                        'source': 'DEPOSIT',
                        'agentId': '26215182921947007384',
                        'datetime': '2026-08-03 19:51:22',
                        'requestId': '2666621500241',
                        'transType': 'CR',
                        'transactionId': '114708362691',
                    }
                ],
            }
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['trans_type'], 'CR')
        self.assertEqual(rows[0]['agent_id'], '26215182921947007384')

    def test_request_id_rejects_dep_prefix(self):
        from apps.bbps.service_flow.deposit_service import _normalize_request_id

        bad = 'DEP20260806072316334EDF72'
        fixed = _normalize_request_id(bad)
        self.assertEqual(len(fixed), 35)
        self.assertNotEqual(fixed, bad)
        self.assertTrue(fixed.isalnum())


class DepositEnquiryFlowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9111999001',
            email='dep.admin@example.com',
            password='TestPass123!',
            role='Admin',
            user_id='DEPADM1',
        )
        cfg = get_or_create_billavenue_mode_row('prod')
        cfg.enabled = True
        cfg.save()
        activate_billavenue_config(cfg)
        BillAvenueAgentProfile.objects.create(
            config=cfg,
            name='AGT default',
            agent_id='CC01RS18AGTBBH294611',
            init_channel='AGT',
            enabled=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    @patch('apps.bbps.service_flow.deposit_service.BBPSClient')
    def test_enquire_persists_snapshot(self, mock_cls):
        mock_cls.return_value.enquire_deposits.return_value = {
            'currency': 'INR',
            'instituteId': 'RS18',
            'responseCode': '000',
            'currentBalance': '1500.50',
            'transaction': [
                {
                    'amount': 500,
                    'source': 'DEPOSIT',
                    'agentId': 'CC01RS18AGTBBH294611',
                    'datetime': '2026-08-01 10:00:00',
                    'requestId': 'REQ1',
                    'transType': 'CR',
                    'transactionId': 'TX1',
                }
            ],
        }
        out = enquire_deposits(
            from_date='2026-07-01',
            to_date='2026-08-01',
            agents=['CC01RS18AGTBBH294611'],
            admin_user=self.admin,
        )
        self.assertEqual(out['current_balance'], '1500.5000')
        self.assertEqual(len(out['transactions']), 1)
        shot = BbpsDepositEnquirySnapshot.objects.get(pk=out['snapshot_id'])
        self.assertEqual(shot.transaction_count, 1)
        self.assertEqual(shot.status, 'SUCCESS')
        self.assertEqual(shot.agents, ['CC01RS18AGTBBH294611'])

    @patch('apps.bbps.service_flow.deposit_service.BBPSClient')
    def test_history_and_detail_api(self, mock_cls):
        mock_cls.return_value.enquire_deposits.return_value = {
            'currency': 'INR',
            'responseCode': '000',
            'currentBalance': '10.00',
            'transaction': [],
        }
        run = self.client.post(
            '/api/bbps/admin/deposit-enquiry/',
            {
                'from_date': '2026-07-01',
                'to_date': '2026-08-01',
                'agents': ['CC01RS18AGTBBH294611'],
            },
            format='json',
        )
        self.assertEqual(run.status_code, 200, run.content)
        sid = run.data['data']['snapshot_id']

        hist = self.client.get('/api/bbps/admin/deposit-enquiry/history/')
        self.assertEqual(hist.status_code, 200)
        self.assertGreaterEqual(hist.data['data']['pagination']['total'], 1)
        self.assertTrue(any(a['agent_id'] == 'CC01RS18AGTBBH294611' for a in hist.data['data']['agent_options']))

        detail = self.client.get(f'/api/bbps/admin/deposit-enquiry/{sid}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['data']['snapshot']['id'], sid)

    def test_retailer_forbidden(self):
        retailer = User.objects.create_user(
            phone='9111999002',
            email='dep.ret@example.com',
            password='TestPass123!',
            role='Retailer',
            user_id='DEPRET1',
        )
        c = APIClient()
        c.force_authenticate(user=retailer)
        self.assertEqual(c.get('/api/bbps/admin/deposit-enquiry/history/').status_code, 403)
