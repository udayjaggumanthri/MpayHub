"""Default passbook filters include historical BBPS without rewriting rows."""
from decimal import Decimal
from unittest.mock import Mock

from django.test import TestCase

from apps.authentication.models import User
from apps.transactions.models import PassbookEntry
from apps.transactions.report_filters import apply_passbook_report_filters
from apps.transactions.reporting_scope import get_operational_report_scope, get_report_scope


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


class PassbookReportFilterTests(TestCase):
    def setUp(self):
        self.user = _user('9000000201', 'pbfilter@test.com', 'Retailer', 'PBFILT1')
        self.main = PassbookEntry.objects.create(
            user=self.user,
            wallet_type='main',
            service='LOAD MONEY',
            service_id='LM-1',
            description='load',
            credit_amount=Decimal('100'),
            debit_amount=Decimal('0'),
            opening_balance=Decimal('0'),
            closing_balance=Decimal('100'),
        )
        self.bbps = PassbookEntry.objects.create(
            user=self.user,
            wallet_type='bbps',
            service='BBPS',
            service_id='BP-1',
            description='bill',
            credit_amount=Decimal('0'),
            debit_amount=Decimal('50'),
            opening_balance=Decimal('100'),
            closing_balance=Decimal('50'),
        )
        self.commission = PassbookEntry.objects.create(
            user=self.user,
            wallet_type='commission',
            service='COMMISSION',
            service_id='CM-1',
            description='earn',
            credit_amount=Decimal('10'),
            debit_amount=Decimal('0'),
            opening_balance=Decimal('0'),
            closing_balance=Decimal('10'),
        )
        self.profit = PassbookEntry.objects.create(
            user=self.user,
            wallet_type='profit',
            service='PROFIT',
            service_id='PR-1',
            description='profit',
            credit_amount=Decimal('5'),
            debit_amount=Decimal('0'),
            opening_balance=Decimal('0'),
            closing_balance=Decimal('5'),
        )

    def _apply(self, **params):
        req = Mock()
        req.query_params = params
        return apply_passbook_report_filters(PassbookEntry.objects.filter(user=self.user), req)

    def test_default_includes_main_and_bbps_excludes_commission_profit(self):
        types = set(self._apply().values_list('wallet_type', flat=True))
        self.assertEqual(types, {'main', 'bbps'})

    def test_include_legacy_shows_commission_and_profit(self):
        types = set(self._apply(include_legacy='true').values_list('wallet_type', flat=True))
        self.assertEqual(types, {'main', 'bbps', 'commission', 'profit'})

    def test_explicit_wallet_type_still_honored(self):
        types = set(self._apply(wallet_type='bbps').values_list('wallet_type', flat=True))
        self.assertEqual(types, {'bbps'})


class OperationalScopeCoerceTests(TestCase):
    def test_admin_self_stays_self_on_passbook_but_platform_on_operational(self):
        admin = _user('9000000202', 'opscope@test.com', 'Admin', 'OPADM1')
        req = Mock()
        req.user = admin
        req.query_params = {'scope': 'self'}
        self.assertEqual(get_report_scope(req), 'self')
        self.assertEqual(get_operational_report_scope(req), 'platform')
        req2 = Mock()
        req2.user = admin
        req2.query_params = {'scope': 'self'}
        self.assertEqual(get_report_scope(req2), 'self')
