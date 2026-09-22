"""Inbound wallet-check / wallet-debit contract tests."""
from __future__ import annotations

import json
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.cms.models import CmsAgentProfile, CmsProviderConfig, CmsTransaction, CmsWallet
from apps.cms.services.crypto import build_inbound_hash
from apps.cms.services.entitlement import enable_entitlement
from apps.cms.services.registry import invalidate_cms_config_cache
from apps.cms.services import wallet as wallet_svc
from apps.core.utils import encrypt_secret_payload
from apps.wallets.models import Wallet


@override_settings(
    INTEGRATION_SECRETS_KEY='dGVzdC1rZXktMzItYnl0ZXMtbG9uZyEhISE=',
)
class CmsInboundTests(TestCase):
    def setUp(self):
        invalidate_cms_config_cache()
        self.secret = '1234567890'
        self.skey = 'NDU2ZmEyNTQzNDQ2Y2RhMTgwM2I0ZWRlMzJjZDkyM2I='
        CmsProviderConfig.objects.create(
            name='default',
            environment='uat',
            is_active=True,
            super_merchant_id='1501',
            cms_base_url='https://fpuat.tapits.in',
            secrets_encrypted=encrypt_secret_payload(
                {'super_merchant_skey': self.skey, 'secret_key': self.secret}
            ),
            hash_template='{payload}{secret_key}',
            allowed_inbound_ips=[],
        )
        self.admin = User.objects.create_user(
            phone='9000000099',
            email='cmsadmin@test.local',
            password='testpass123',
            role='Admin',
            first_name='Admin',
        )
        self.retailer = User.objects.create_user(
            phone='9000000098',
            email='cmsretailer@test.local',
            password='testpass123',
            role='Retailer',
            first_name='Retailer',
        )
        enable_entitlement(actor=self.admin, user=self.retailer)
        self.agent = CmsAgentProfile.objects.get(user=self.retailer)
        # CMS holds use the shared main wallet after consolidation.
        main = Wallet.get_wallet(self.retailer, 'main')
        main.credit(Decimal('1000.00'), reference='cms-test-seed')
        self.client = APIClient()

    def _post(self, path, body: dict):
        raw = json.dumps(body, separators=(',', ':'))
        h = build_inbound_hash(raw, self.secret)
        return self.client.post(
            path,
            data=raw,
            content_type='application/json',
            HTTP_HASH=h,
        )

    def test_wallet_check_returns_balance(self):
        r = self._post(
            '/api/cms/webhooks/fingpay/wallet-check/',
            {'bcLoginIds': [self.agent.bc_login_id, 'UNKNOWN']},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['status'])
        bals = {b['bcLoginId']: b['balance'] for b in r.data['bcBalances']}
        self.assertIn(self.agent.bc_login_id, bals)
        self.assertNotIn('UNKNOWN', bals)
        self.assertEqual(float(bals[self.agent.bc_login_id]), 1000.0)

    def test_wallet_debit_i_s_f_flow(self):
        initiate = {
            'amount': 100.0,
            'transactionStatus': 'I',
            'fpTransactionId': 'FP00187352S',
            'typeOfTransaction': 'CDC',
            'bcLoginId': self.agent.bc_login_id,
            'transactionTimestamp': '2021-07-21 12:23:56',
            'errorMessage': 'Transaction initiated',
            'remarks': '',
        }
        r = self._post('/api/cms/webhooks/fingpay/wallet-debit/', initiate)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['status'])
        mid = r.data['merchantTransactionId']
        self.assertTrue(mid)
        txn = CmsTransaction.objects.get(fp_transaction_id='FP00187352S')
        self.assertEqual(txn.status, 'initiated')
        main = Wallet.get_wallet(self.retailer, 'main')
        self.assertEqual(main.held_balance, Decimal('100.0000'))

        # Idempotent I
        r2 = self._post('/api/cms/webhooks/fingpay/wallet-debit/', initiate)
        self.assertTrue(r2.data['status'])
        self.assertEqual(r2.data['merchantTransactionId'], mid)
        self.assertEqual(CmsTransaction.objects.filter(fp_transaction_id='FP00187352S').count(), 1)

        success = {
            **initiate,
            'transactionStatus': 'S',
            'merchantTransactionId': mid,
            'errorMessage': 'Transaction is success',
        }
        r3 = self._post('/api/cms/webhooks/fingpay/wallet-debit/', success)
        self.assertTrue(r3.data['status'])
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'success')
        main.refresh_from_db()
        self.assertEqual(main.held_balance, Decimal('0.0000'))
        self.assertEqual(main.balance, Decimal('900.0000'))

    def test_wallet_debit_fail_releases_hold(self):
        initiate = {
            'amount': 50.0,
            'transactionStatus': 'I',
            'fpTransactionId': 'FPFAIL001',
            'typeOfTransaction': 'CDC',
            'bcLoginId': self.agent.bc_login_id,
            'transactionTimestamp': '2021-07-21 12:23:56',
            'errorMessage': 'Transaction initiated',
            'remarks': '',
        }
        r = self._post('/api/cms/webhooks/fingpay/wallet-debit/', initiate)
        mid = r.data['merchantTransactionId']
        fail = {
            **initiate,
            'transactionStatus': 'F',
            'merchantTransactionId': mid,
            'errorMessage': 'failed',
        }
        self._post('/api/cms/webhooks/fingpay/wallet-debit/', fail)
        txn = CmsTransaction.objects.get(fp_transaction_id='FPFAIL001')
        self.assertEqual(txn.status, 'failed')
        main = Wallet.get_wallet(self.retailer, 'main')
        self.assertEqual(main.held_balance, Decimal('0.0000'))
        self.assertEqual(main.balance, Decimal('1000.0000'))

    def test_insufficient_balance(self):
        body = {
            'amount': 99999.0,
            'transactionStatus': 'I',
            'fpTransactionId': 'FPBIG',
            'typeOfTransaction': 'CDC',
            'bcLoginId': self.agent.bc_login_id,
            'transactionTimestamp': '2021-07-21 12:23:56',
            'errorMessage': 'Transaction initiated',
            'remarks': '',
        }
        r = self._post('/api/cms/webhooks/fingpay/wallet-debit/', body)
        self.assertFalse(r.data['status'])
        self.assertIn('Insufficient', r.data['errorMessage'])

    def test_bad_hash_rejected(self):
        raw = json.dumps({'bcLoginIds': [self.agent.bc_login_id]})
        r = self.client.post(
            '/api/cms/webhooks/fingpay/wallet-check/',
            data=raw,
            content_type='application/json',
            HTTP_HASH='not-a-valid-hash',
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['status'])
        self.assertIn('hash', r.data['errorMessage'].lower())
