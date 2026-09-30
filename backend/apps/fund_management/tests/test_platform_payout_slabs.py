"""Platform-wide payout slabs: Charge + Commission."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.fund_management.models import PlatformPayoutSlabTier
from apps.fund_management.services import payout_slab_breakdown_for_amount
from apps.transactions.models import CommissionLedger
from apps.transactions.services.fee_settlement import settle_service_charge
from apps.wallets.models import Wallet

User = get_user_model()


class PlatformPayoutSlabBreakdownTests(TestCase):
    def setUp(self):
        PlatformPayoutSlabTier.objects.all().delete()
        PlatformPayoutSlabTier.objects.create(
            sort_order=0,
            min_amount=Decimal('0'),
            max_amount=Decimal('1000'),
            charge=Decimal('4.5'),
            commission=Decimal('11.5'),
        )
        PlatformPayoutSlabTier.objects.create(
            sort_order=1,
            min_amount=Decimal('1000.01'),
            max_amount=Decimal('3000'),
            charge=Decimal('8'),
            commission=Decimal('12'),
        )
        PlatformPayoutSlabTier.objects.create(
            sort_order=2,
            min_amount=Decimal('3000.01'),
            max_amount=None,
            charge=Decimal('10'),
            commission=Decimal('20'),
        )

    def test_breakdown_sums_charge_and_commission(self):
        bd = payout_slab_breakdown_for_amount(Decimal('500'))
        self.assertEqual(bd['charge'], Decimal('4.5000'))
        self.assertEqual(bd['commission'], Decimal('11.5000'))
        self.assertEqual(bd['total'], Decimal('16.0000'))  # 4.5+11.5

    def test_mid_and_high_bands(self):
        mid = payout_slab_breakdown_for_amount(Decimal('2000'))
        self.assertEqual(mid['total'], Decimal('20.0000'))
        high = payout_slab_breakdown_for_amount(Decimal('5000'))
        self.assertEqual(high['charge'], Decimal('10.0000'))
        self.assertEqual(high['commission'], Decimal('20.0000'))
        self.assertEqual(high['total'], Decimal('30.0000'))


@override_settings(PLATFORM_PAYIN_SETTLEMENT_USER_ID=None)
class PayoutSettlementSplitTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9011111101',
            email='pslab_admin@test.local',
            password='TestPass1!',
            role='Admin',
            user_id='PSLAB_AD',
        )
        self.payer = User.objects.create_user(
            phone='9011111102',
            email='pslab_payer@test.local',
            password='TestPass1!',
            role='Retailer',
            user_id='PSLAB_RT',
        )
        Wallet.get_wallet(self.admin, 'main')
        Wallet.get_wallet(self.payer, 'main').credit(Decimal('1000'), reference='seed')

    def test_charge_only_tracker_no_main_credit(self):
        settle_service_charge(
            payer=self.payer,
            module='payout',
            service_id='PMPO-SPLIT-1',
            charge=Decimal('7'),
            principal=Decimal('500'),
            slices=[{
                'user': self.admin,
                'amount': Decimal('7'),
                'slice_key': 'platform_fee',
                'entry_kind': 'service_fee',
                'source': 'payout',
            }],
        )
        self.assertEqual(Wallet.get_wallet(self.admin, 'main').balance, Decimal('0.0000'))
        row = CommissionLedger.objects.get(reference_service_id='PMPO-SPLIT-1')
        self.assertEqual(row.entry_kind, 'service_fee')

    def test_commission_slice_credits_treasury(self):
        settle_service_charge(
            payer=self.payer,
            module='payout',
            service_id='PMPO-SPLIT-2',
            charge=Decimal('15'),
            principal=Decimal('500'),
            slices=[
                {
                    'user': self.admin,
                    'amount': Decimal('4.5'),
                    'slice_key': 'platform_fee',
                    'entry_kind': 'service_fee',
                    'source': 'payout',
                },
                {
                    'user': self.admin,
                    'amount': Decimal('10.5'),
                    'slice_key': 'payout_admin',
                    'entry_kind': 'commission',
                    'source': 'payout',
                    'service_label': 'COMMISSION',
                },
            ],
        )
        self.assertEqual(Wallet.get_wallet(self.admin, 'main').balance, Decimal('10.5000'))
        kinds = set(
            CommissionLedger.objects.filter(reference_service_id='PMPO-SPLIT-2')
            .values_list('entry_kind', flat=True)
        )
        self.assertEqual(kinds, {'service_fee', 'commission'})


class PlatformPayoutSlabsAdminApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9011111103',
            email='pslab_api@test.local',
            password='TestPass1!',
            role='Admin',
            user_id='PSLAB_API',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        PlatformPayoutSlabTier.objects.all().delete()

    def test_put_replace_all(self):
        res = self.client.put(
            '/api/admin/payout-slabs/',
            {
                'slabs': [
                    {
                        'min_amount': '0',
                        'max_amount': '1000',
                        'charge': '4.5',
                        'commission': '11.5',
                    },
                    {
                        'min_amount': '1000.01',
                        'max_amount': None,
                        'charge': '8',
                        'commission': '12',
                    },
                ]
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        self.assertEqual(len(res.data['data']['slabs']), 2)
        self.assertEqual(res.data['data']['slabs'][0]['total'], '16.0000')
        get_res = self.client.get('/api/admin/payout-slabs/')
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(len(get_res.data['data']['slabs']), 2)
