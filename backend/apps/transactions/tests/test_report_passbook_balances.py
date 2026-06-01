"""Tests for report passbook balance batch lookup."""
from decimal import Decimal

from django.test import TestCase

from apps.authentication.models import User
from apps.transactions.models import PassbookEntry
from apps.transactions.report_passbook_balances import (
    bbps_balance_map,
    payin_balance_map_for_transactions,
    payout_balance_map,
)


def _user(phone, email, role, user_id):
    return User.objects.create_user(
        phone=phone,
        email=email,
        password='testpass123',
        role=role,
        user_id=user_id,
        first_name='T',
        last_name='User',
    )


class _TxnStub:
    def __init__(self, service_id, user_id):
        self.service_id = service_id
        self.user_id = user_id


class ReportPassbookBalanceTests(TestCase):
    def setUp(self):
        self.user = _user('9000000101', 'bal@test.com', 'Retailer', 'BALRET1')

    def _entry(self, *, service_id, service, wallet_type, credit=0, debit=0, opening='100', closing='200'):
        return PassbookEntry.objects.create(
            user=self.user,
            wallet_type=wallet_type,
            service=service,
            service_id=service_id,
            description='test',
            credit_amount=Decimal(str(credit)),
            debit_amount=Decimal(str(debit)),
            opening_balance=Decimal(opening),
            closing_balance=Decimal(closing),
        )

    def test_payin_balance_map_returns_latest_credit_row(self):
        self._entry(
            service_id='LM-1',
            service='LOAD MONEY',
            wallet_type='main',
            credit=500,
            opening='1000.0000',
            closing='1500.0000',
        )
        self._entry(
            service_id='LM-1',
            service='LOAD MONEY',
            wallet_type='main',
            credit=100,
            opening='1500.0000',
            closing='1600.0000',
        )
        result = payin_balance_map_for_transactions([_TxnStub('LM-1', self.user.id)])
        key = ('LM-1', self.user.id)
        self.assertEqual(result[key].opening, '1500.0000')
        self.assertEqual(result[key].closing, '1600.0000')

    def test_payout_balance_map_uses_debit_payout_line(self):
        self._entry(
            service_id='PO-1',
            service='PAYOUT',
            wallet_type='main',
            debit=50,
            opening='500.0000',
            closing='450.0000',
        )
        result = payout_balance_map([_TxnStub('PO-1', self.user.id)])
        key = ('PO-1', self.user.id)
        self.assertEqual(result[key].opening, '500.0000')
        self.assertEqual(result[key].closing, '450.0000')

    def test_bbps_balance_map_uses_bbps_wallet(self):
        self._entry(
            service_id='BP-1',
            service='BBPS',
            wallet_type='bbps',
            debit=25,
            opening='300.0000',
            closing='275.0000',
        )
        result = bbps_balance_map([_TxnStub('BP-1', self.user.id)])
        key = ('BP-1', self.user.id)
        self.assertEqual(result[key].opening, '300.0000')
        self.assertEqual(result[key].closing, '275.0000')

    def test_missing_passbook_returns_empty_pair(self):
        result = payin_balance_map_for_transactions([_TxnStub('MISSING', self.user.id)])
        key = ('MISSING', self.user.id)
        self.assertEqual(result[key].opening, '')
        self.assertEqual(result[key].closing, '')
