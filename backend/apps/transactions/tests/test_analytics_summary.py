"""Tests for platform-wide gateway analytics (all users)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.fund_management.models import LoadMoney
from apps.transactions.analytics_summary import get_gateway_analytics_summary

User = get_user_model()


def _create_user(**kwargs):
    defaults = {
        'password': 'testpass123',
        'role': 'Retailer',
        'first_name': 'T',
        'last_name': 'U',
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


class GatewayAnalyticsPlatformScopeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = _create_user(
            phone='9111000001',
            email='admin_analytics@test.com',
            role='Admin',
            user_id='ADM1',
        )
        self.retailer_a = _create_user(
            phone='9111000002',
            email='ret_a_analytics@test.com',
            user_id='RTA1',
        )
        self.retailer_b = _create_user(
            phone='9111000003',
            email='ret_b_analytics@test.com',
            user_id='RTB1',
        )
        from django.utils import timezone

        self.today = timezone.localdate().isoformat()

    def _lm(self, user, tid, amount):
        return LoadMoney.objects.create(
            user=user,
            amount=Decimal(amount),
            gateway='Razorpay',
            charge=Decimal('10'),
            net_credit=Decimal(amount) - Decimal('10'),
            status='SUCCESS',
            transaction_id=tid,
        )

    def test_aggregates_all_users_not_admin_only(self):
        self._lm(self.retailer_a, 'LM-A-1', '5000')
        self._lm(self.retailer_b, 'LM-B-1', '3000')
        self._lm(self.admin, 'LM-ADM-1', '2000')

        data = get_gateway_analytics_summary(
            interval='daily',
            date_from_raw=self.today,
            date_to_raw=self.today,
        )
        self.assertEqual(data['scope'], 'platform')
        self.assertEqual(data['totals']['transactions_count'], 3)
        self.assertEqual(Decimal(data['totals']['payin_sales']), Decimal('10000'))

    def test_admin_api_returns_platform_scope(self):
        self._lm(self.retailer_a, 'LM-A-2', '1000')
        client = APIClient()
        client.force_authenticate(user=self.admin)
        url = reverse('reports:analytics-summary')
        res = client.get(url, {'date_from': self.today, 'date_to': self.today})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['data']['scope'], 'platform')
        self.assertGreaterEqual(res.data['data']['totals']['transactions_count'], 1)

    def test_groups_by_gateway_without_loading_each_row_in_python(self):
        self._lm(self.retailer_a, 'LM-GW-A', '1000')
        lm_b = self._lm(self.retailer_b, 'LM-GW-B', '2000')
        lm_b.gateway = 'PayU'
        lm_b.save(update_fields=['gateway'])

        data = get_gateway_analytics_summary(
            interval='daily',
            date_from_raw=self.today,
            date_to_raw=self.today,
            use_cache=False,
        )
        by_gw = {r['gateway']: r for r in data['rows']}
        self.assertIn('Razorpay', by_gw)
        self.assertIn('PayU', by_gw)
        self.assertEqual(by_gw['Razorpay']['transactions_count'], 1)
        self.assertEqual(by_gw['PayU']['transactions_count'], 1)
        self.assertEqual(data['totals']['transactions_count'], 2)

    def test_non_admin_forbidden(self):
        client = APIClient()
        client.force_authenticate(user=self.retailer_a)
        url = reverse('reports:analytics-summary')
        res = client.get(url)
        self.assertEqual(res.status_code, 403)
