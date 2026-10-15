import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.admin_panel.models import PaymentGateway
from apps.contacts.models import Contact
from apps.core.utils import encrypt_secret_payload
from apps.fund_management.hub_result import payment_result_view
from apps.fund_management.models import PayInPackage, UserPackageAssignment
from apps.fund_management.package_gateways import sync_package_gateway_links
from apps.fund_management.services import create_payin_order
from apps.fund_management.toucan_hub import check_toucan_payin, hub_gate_open, start_toucan_payin
from apps.integrations.models import ApiMaster

User = get_user_model()


def _signed(secret, body):
    raw = json.dumps(body).encode('utf-8')
    timestamp = str(int(time.time()))
    signature = hmac.new(secret.encode('utf-8'), f'{timestamp}.'.encode('utf-8') + raw, hashlib.sha256).hexdigest()
    return raw, timestamp, signature


class ToucanHubClientTests(TestCase):
    def test_live_toucan_payin_stays_off(self):
        self.assertFalse(hub_gate_open())

    def test_start_refuses_when_the_gate_is_closed(self):
        load_money = type('LM', (), {'pk': 1, 'transaction_id': 'LM1', 'amount': '10'})()
        with patch('apps.fund_management.toucan_hub.LoadMoney.objects.filter') as filtered:
            with self.assertRaises(Exception) as caught:
                start_toucan_payin(load_money, type('C', (), {'name': 'A', 'phone': '1', 'email': 'a@b.c'})(), {})
        self.assertIn('not enabled', str(caught.exception))
        filtered.return_value.update.assert_called()

    def test_status_check_posts_the_invoice_to_the_hub(self):
        load_money = type('LM', (), {
            'transaction_id': 'PMLM1',
            'provider_order_id': '1210202612000011111',
            'collection_rail': 'gateway',
            'payment_method': 'toucan',
            'payment_gateway': None,
        })()
        opener = MagicMock()
        opener.read.return_value = b'{"payment_status":"SUCCESS","action_code":"00","message":"Toucan confirmed this payment."}'
        opener.__enter__.return_value = opener
        with patch(
            'apps.fund_management.toucan_hub._hub_credentials',
            return_value=('https://hub.example', 'key', 'secret'),
        ):
            with patch('apps.fund_management.toucan_hub.urllib.request.urlopen', return_value=opener) as opened:
                data = check_toucan_payin(load_money)
        self.assertEqual(data['action_code'], '00')
        request = opened.call_args[0][0]
        self.assertTrue(request.full_url.endswith('/api/v1/payments/status-check'))
        posted = json.loads(request.data.decode())
        self.assertEqual(posted['invoice'], '1210202612000011111')
        self.assertEqual(posted['application_order_id'], 'PMLM1')

    @patch('apps.fund_management.hub_result.finalize_payin_success')
    @patch('apps.fund_management.hub_result.LoadMoney.objects.filter')
    def test_signed_result_settles_through_finalize(self, filtered, finalize):
        load_money = type('LM', (), {'transaction_id': 'LM1', 'status': 'PENDING'})()
        filtered.return_value.first.return_value = load_money
        body = {'application_order_id': 'LM1', 'payment_status': 'SUCCESS', 'invoice': '123456789012345'}
        raw, timestamp, signature = _signed('test-secret', body)
        request = RequestFactory().post(
            '/api/payment/result',
            data=raw,
            content_type='application/json',
            HTTP_X_HUB_TIMESTAMP=timestamp,
            HTTP_X_HUB_SIGNATURE=signature,
        )
        with patch.dict('os.environ', {'PAYMENT_HUB_HMAC_SECRET': 'test-secret'}):
            response = payment_result_view(request)
        self.assertEqual(response.status_code, 200)
        finalize.assert_called_once()
        self.assertEqual(finalize.call_args.kwargs['payment_method'], 'toucan')


class ToucanRailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555599',
            email='toucan-rail@test.com',
            password='testpass123',
            role='Retailer',
            user_id='TCHUB1',
            first_name='T',
            last_name='User',
        )
        self.contact = Contact.objects.create(
            user=self.user,
            name='Test Customer',
            email='cust@test.com',
            phone='9876543210',
        )

    def _assign(self, package):
        UserPackageAssignment.objects.create(user=self.user, package=package)

    def _package(self, code, provider):
        return PayInPackage.objects.create(
            code=code,
            display_name=code,
            provider=provider,
            gateway_fee_pct=Decimal('1.0000'),
            admin_pct=Decimal('0'),
            super_distributor_pct=Decimal('0'),
            master_distributor_pct=Decimal('0'),
            distributor_pct=Decimal('0'),
            retailer_commission_pct=Decimal('0'),
            is_default=False,
        )

    def test_mock_package_does_not_call_the_hub(self):
        package = self._package('qr_like', 'mock')
        gateway = PaymentGateway.objects.create(
            name='QR package gateway',
            charge_rate=Decimal('1.00'),
            status='active',
            visible_to_roles=['Retailer'],
        )
        sync_package_gateway_links(package, [gateway.id], default_gateway_id=gateway.id)
        self._assign(package)
        with patch('apps.fund_management.toucan_hub.start_toucan_payin') as hub:
            _lm, payload = create_payin_order(
                self.user,
                package_id=package.id,
                gross=Decimal('100.00'),
                contact_id=self.contact.id,
                gateway_id=gateway.id,
            )
        hub.assert_not_called()
        self.assertTrue(payload.get('mock'))
        self.assertEqual(payload['provider'], 'mock')

    @patch('apps.integrations.razorpay_orders.create_order', return_value=({'id': 'order_rz', 'amount': 10000, 'currency': 'INR'}, None))
    @patch('apps.fund_management.services._razorpay_keypair_for_payin_package', return_value=('rz_key', 'rz_secret'))
    def test_razorpay_gateway_still_creates_a_razorpay_order(self, _keys, create_order):
        master = ApiMaster.objects.create(
            provider_code='razorpay',
            provider_name='Razorpay',
            provider_type='payments',
            status='active',
            base_url='https://api.razorpay.com',
        )
        package = self._package('rz_pkg', 'razorpay')
        gateway = PaymentGateway.objects.create(
            name='Razorpay',
            charge_rate=Decimal('1.00'),
            status='active',
            visible_to_roles=['Retailer'],
            api_master=master,
        )
        sync_package_gateway_links(package, [gateway.id], default_gateway_id=gateway.id)
        self._assign(package)
        with patch('apps.fund_management.toucan_hub.start_toucan_payin') as hub:
            _lm, payload = create_payin_order(
                self.user,
                package_id=package.id,
                gross=Decimal('100.00'),
                contact_id=self.contact.id,
                gateway_id=gateway.id,
            )
        hub.assert_not_called()
        create_order.assert_called_once()
        self.assertEqual(payload['provider'], 'razorpay')
        self.assertEqual(payload['razorpay']['order_id'], 'order_rz')

    def test_toucan_gateway_calls_the_hub_with_api_master_key(self):
        master = ApiMaster.objects.create(
            provider_code='toucan',
            provider_name='Toucan payment hub',
            provider_type='payments',
            status='active',
            base_url='https://uat.prajnadharaedu.com',
            secrets_encrypted=encrypt_secret_payload({'api_key': 'hub-key-1', 'hmac_secret': 'hub-secret-1'}),
        )
        package = self._package('qr_and_hub', 'mock')
        gateway = PaymentGateway.objects.create(
            name='Toucan',
            charge_rate=Decimal('1.00'),
            status='active',
            visible_to_roles=['Retailer'],
            api_master=master,
        )
        sync_package_gateway_links(package, [gateway.id], default_gateway_id=gateway.id)
        self._assign(package)
        opener = MagicMock()
        opener.read.return_value = b'{"redirect_url":"https://pay.example/checkout","invoice":"123456789012345"}'
        opener.__enter__.return_value = opener
        with patch.dict('os.environ', {'PAYMENT_HUB_TOUCAN_ENABLED': 'false'}, clear=False):
            with patch('apps.fund_management.toucan_hub.urllib.request.urlopen', return_value=opener) as opened:
                _lm, payload = create_payin_order(
                    self.user,
                    package_id=package.id,
                    gross=Decimal('100.00'),
                    contact_id=self.contact.id,
                    gateway_id=gateway.id,
                )
        self.assertEqual(payload['provider'], 'toucan')
        self.assertEqual(payload['redirect_url'], 'https://pay.example/checkout')
        request = opened.call_args[0][0]
        self.assertEqual(request.get_header('Authorization'), 'Bearer hub-key-1')
        self.assertEqual(request.get_header('User-agent'), 'mPayHub-PaymentHub/1.0')
        self.assertTrue(request.full_url.startswith('https://uat.prajnadharaedu.com/api/v1/payments'))

    @patch('apps.fund_management.hub_result.finalize_payin_success')
    @patch('apps.fund_management.hub_result.LoadMoney.objects.filter')
    def test_result_accepts_api_master_hmac(self, filtered, finalize):
        load_money = type('LM', (), {'transaction_id': 'LM9', 'status': 'PENDING'})()
        filtered.return_value.first.return_value = load_money
        ApiMaster.objects.create(
            provider_code='toucan',
            provider_name='Toucan payment hub',
            provider_type='payments',
            status='active',
            base_url='https://uat.prajnadharaedu.com',
            secrets_encrypted=encrypt_secret_payload({'api_key': 'hub-key-1', 'hmac_secret': 'master-secret'}),
        )
        body = {'application_order_id': 'LM9', 'payment_status': 'SUCCESS', 'invoice': '123456789012345'}
        raw, timestamp, signature = _signed('master-secret', body)
        request = RequestFactory().post(
            '/api/payment/result',
            data=raw,
            content_type='application/json',
            HTTP_X_HUB_TIMESTAMP=timestamp,
            HTTP_X_HUB_SIGNATURE=signature,
        )
        with patch.dict('os.environ', {'PAYMENT_HUB_HMAC_SECRET': ''}, clear=False):
            response = payment_result_view(request)
        self.assertEqual(response.status_code, 200)
        finalize.assert_called_once()
