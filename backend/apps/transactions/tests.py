from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from apps.transactions.reporting_scope import (
    get_report_scope,
    team_transaction_user_ids,
    transaction_user_q,
)
from apps.users.models import UserHierarchy

from apps.transactions.report_api import money_str

User = get_user_model()


class ReportScopeTests(TestCase):
    def setUp(self):
        self.retailer = User.objects.create_user(
            phone='9333333333',
            email='rep_scope@test.com',
            password='testpass123',
            role='Retailer',
            user_id='RTS1',
            first_name='R',
            last_name='S',
        )

    def test_retailer_team_scope_forbidden(self):
        req = Mock()
        req.user = self.retailer
        req.query_params = {'scope': 'team'}
        self.assertEqual(get_report_scope(req), 'team')
        with self.assertRaises(PermissionDenied):
            transaction_user_q(req)

    def test_retailer_self_scope_ok(self):
        req = Mock()
        req.user = self.retailer
        req.query_params = {'scope': 'self'}
        q = transaction_user_q(req)
        self.assertEqual(q, Q(user=self.retailer))


class TeamTransactionUserIdsTests(TestCase):
    """Distributor team scope includes self + Retailer downline only (not other distributors)."""

    def setUp(self):
        self.dt = User.objects.create_user(
            phone='9111111111',
            email='dt_scope@test.com',
            password='testpass123',
            role='Distributor',
            user_id='DTS1',
            first_name='D',
            last_name='T',
        )
        self.rt = User.objects.create_user(
            phone='9222222222',
            email='rt_scope@test.com',
            password='testpass123',
            role='Retailer',
            user_id='RTS2',
            first_name='R',
            last_name='T',
        )
        self.other_dt = User.objects.create_user(
            phone='9444444444',
            email='odt_scope@test.com',
            password='testpass123',
            role='Distributor',
            user_id='DTS2',
            first_name='O',
            last_name='D',
        )
        UserHierarchy.objects.create(parent_user=self.dt, child_user=self.rt)
        UserHierarchy.objects.create(parent_user=self.dt, child_user=self.other_dt)

    def test_distributor_team_includes_only_retailers_plus_self(self):
        ids = team_transaction_user_ids(self.dt)
        self.assertIn(self.dt.pk, ids)
        self.assertIn(self.rt.pk, ids)
        self.assertNotIn(self.other_dt.pk, ids)


class MoneyPrecisionTests(TestCase):
    def test_money_str_four_decimals(self):
        from decimal import Decimal

        self.assertEqual(money_str(Decimal('1.2')), '1.2000')
        self.assertEqual(money_str(Decimal('10.12345')), '10.1235')  # ROUND_HALF_UP
