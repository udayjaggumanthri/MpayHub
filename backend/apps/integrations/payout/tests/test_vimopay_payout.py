"""Unit tests for VimoPay payout crypto, status mapping, masters matching, and orchestrator."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.authentication.models import User
from apps.bank_accounts.models import BankAccount
from apps.core.utils import encrypt_secret_payload
from apps.fund_management.models import Payout, PayoutProviderEvent
from apps.fund_management.payout_orchestrator import apply_payout_callback, process_payout
from apps.integrations.models import ApiMaster
from apps.integrations.payout import crypto as vimopay_crypto
from apps.integrations.payout.masters_cache import match_bank_code, match_state_code
from apps.integrations.payout.types import (
    DOMAIN_FAILED,
    DOMAIN_PENDING,
    DOMAIN_SUCCESS,
    MasterItem,
    PayoutCallbackEvent,
    PayoutInitiateResult,
    map_provider_status_code,
)
from apps.wallets.models import Wallet


def _masters_side_effect(provider, kind, **_kwargs):
    if kind == 'banks':
        return provider.list_banks()
    if kind == 'states':
        return provider.list_states()
    return provider.list_purposes()


def _bind_masters(mock_masters, provider):
    mock_masters.side_effect = lambda _provider, kind, **kwargs: _masters_side_effect(provider, kind, **kwargs)


class CryptoTests(TestCase):
    def test_encrypt_decrypt_roundtrip(self):
        # UAT gateway uses secretKey as AES key and saltKey as IV (UTF-8).
        ed = 'f37701ee0778cfe1dd97b7537ae71709'
        iv = 'bb13602c407b1ddd6506d59e410bafeb'
        plain = '{"amount":100.0,"merchantRefId":"TEST123"}'
        cipher = vimopay_crypto.encrypt(plain, ed_key=ed, iv_key=iv)
        self.assertTrue(cipher)
        self.assertNotEqual(cipher, plain)
        back = vimopay_crypto.decrypt(cipher, ed_key=ed, iv_key=iv)
        self.assertEqual(back, plain)


class SanitizeNameTests(TestCase):
    def test_strips_title_and_punctuation(self):
        from apps.integrations.payout.providers.vimopay import sanitize_beneficiary_name

        self.assertEqual(
            sanitize_beneficiary_name('Mr. JAGGUMANTHRI  KUNDAN UDAY KUMAR'),
            'JAGGUMANTHRI KUNDAN UDAY KUMAR',
        )
        self.assertEqual(
            sanitize_beneficiary_name('Mrs. A.B. Sharma-123'),
            'A B Sharma',
        )


class StatusMapTests(TestCase):
    def test_codes(self):
        self.assertEqual(map_provider_status_code('000'), DOMAIN_SUCCESS)
        self.assertEqual(map_provider_status_code('001'), DOMAIN_FAILED)
        self.assertEqual(map_provider_status_code('003'), DOMAIN_FAILED)
        self.assertEqual(map_provider_status_code('002'), DOMAIN_PENDING)
        self.assertEqual(map_provider_status_code('004'), DOMAIN_PENDING)
        self.assertEqual(map_provider_status_code('', txn_status='Success'), DOMAIN_SUCCESS)
        self.assertEqual(map_provider_status_code('', txn_status='Queued'), DOMAIN_PENDING)


class MatchBankCodeTests(TestCase):
    def test_match_by_name_and_ifsc(self):
        banks = [
            MasterItem(code='001', description='Axis Bank'),
            MasterItem(code='013', description='HDFC Bank'),
            MasterItem(code='014', description='ICICI Bank'),
        ]
        self.assertEqual(match_bank_code(banks, bank_name='HDFC Bank'), '013')
        self.assertEqual(match_bank_code(banks, bank_name='hdfc'), '013')
        self.assertEqual(match_bank_code(banks, ifsc='HDFC0000516'), '013')
        self.assertIsNone(match_bank_code(banks, bank_name='Unknown Coop'))


class MatchStateCodeTests(TestCase):
    def test_match_by_code_name_and_iso(self):
        states = [
            MasterItem(code='AP', description='Andhra Pradesh'),
            MasterItem(code='JH', description='Jharkhand'),
            MasterItem(code='DL', description='Delhi'),
        ]
        self.assertEqual(match_state_code(states, 'AP'), 'AP')
        self.assertEqual(match_state_code(states, 'ANDHRA PRADESH'), 'AP')
        self.assertEqual(match_state_code(states, 'IN-AP'), 'AP')
        self.assertEqual(match_state_code(states, 'NCT of Delhi'), 'DL')
        self.assertIsNone(match_state_code(states, 'Unknownland'))


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class PayoutOrchestratorTests(TestCase):
    def setUp(self):
        from apps.core.maintenance_mode import invalidate_cache, update_config

        invalidate_cache()
        update_config(changed_by=None, patch={'payout_enabled': True})
        invalidate_cache()

        self.user = User.objects.create_user(
            phone='9876543299',
            email='payout_orch@test.com',
            password='pass12345',
            role='Retailer',
            user_id='RTPOUT1',
            first_name='Payout',
            last_name='Test',
        )
        self.wallet = Wallet.get_wallet(self.user, 'main')
        self.wallet.balance = Decimal('5000.0000')
        self.wallet.held_balance = Decimal('0')
        self.wallet.save(update_fields=['balance', 'held_balance'])
        self.bank = BankAccount.objects.create(
            user=self.user,
            account_number='50200030251661',
            ifsc='HDFC0000516',
            bank_name='HDFC Bank',
            account_holder_name='Test User',
            beneficiary_name='Test User',
            mobile_number='9876543299',
            is_verified=True,
        )
        self.master = ApiMaster.objects.create(
            provider_code='vimopay',
            provider_name='VimoPay UAT',
            provider_type='payout',
            base_url='http://gateway.vimopay.in',
            status='sandbox',
            is_default=True,
            secrets_encrypted=encrypt_secret_payload(
                {
                    'secret_key': 'f37701ee0778cfe1dd97b7537ae71709',
                    'salt_key': 'bb13602c407b1ddd6506d59e410bafeb',
                    'encrypt_decrypt_key': '47cdba1911f078afe863774a8dffcb26',
                    'user_id': 'E5B82667-9A9D-4A5A-A55C-F3B1E10BF370',
                }
            ),
            config_json={'timeout': 10, 'default_purpose_code': '004'},
            supports_webhook=True,
            webhook_path='/api/integrations/payout/vimopay/callback/',
        )

    def _mock_provider(self):
        provider = MagicMock()
        provider.provider_code = 'vimopay'
        provider.master = self.master
        provider.supported_transfer_modes.return_value = frozenset({'IMPS', 'NEFT'})
        provider.amount_limits.return_value = (Decimal('100'), Decimal('100000'))
        provider.default_purpose_code.return_value = '004'
        provider.normalize_beneficiary_name.side_effect = lambda n: n
        provider.list_banks.return_value = [
            MasterItem(code='013', description='HDFC Bank'),
        ]
        provider.list_states.return_value = [
            MasterItem(code='JH', description='Jharkhand'),
            MasterItem(code='AP', description='Andhra Pradesh'),
            MasterItem(code='WB', description='West Bengal'),
        ]
        provider.list_purposes.return_value = [MasterItem(code='004', description='Payout')]
        provider.initiate.return_value = PayoutInitiateResult(
            domain_status=DOMAIN_PENDING,
            provider_status_code='004',
            provider_txn_id='txn-uuid-1',
            response_message='Your request is been queued',
            charges=Decimal('1.0'),
            raw={},
        )
        return provider

    @patch('apps.fund_management.payout_orchestrator.resolve_payout_provider')
    @patch('apps.fund_management.payout_orchestrator.get_masters')
    @patch('apps.integrations.payout.beneficiary_location.lookup_ifsc_state', return_value='')
    def test_process_payout_holds_until_callback(self, _mock_ifsc, mock_masters, mock_resolve):
        provider = self._mock_provider()
        mock_resolve.return_value = provider
        _bind_masters(mock_masters, provider)

        payout = process_payout(
            self.user,
            self.bank.id,
            Decimal('100'),
            transfer_mode='IMPS',
            beneficiary_location='JH',
            lat='28.7',
            long='77.1',
        )
        self.assertEqual(payout.status, 'PENDING')
        self.assertEqual(payout.provider_txn_id, 'txn-uuid-1')
        self.assertEqual(payout.beneficiary_location, 'JH')
        self.wallet.refresh_from_db()
        # 100 + slab (default 7 for <=24999)
        self.assertGreater(self.wallet.held_balance, 0)
        self.assertEqual(self.wallet.balance, Decimal('5000.0000'))

        # Success callback settles
        event = PayoutCallbackEvent(
            merchant_ref_id=payout.transaction_id,
            domain_status=DOMAIN_SUCCESS,
            provider_status_code='000',
            provider_txn_id='txn-uuid-1',
            rrn='502222116180',
            response_message='Transaction successful',
            raw={'txnStatus': 'Success'},
        )
        apply_payout_callback(event, provider_code='vimopay')
        payout.refresh_from_db()
        self.assertEqual(payout.status, 'SUCCESS')
        self.assertEqual(payout.rrn, '502222116180')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.held_balance, Decimal('0.0000'))
        self.assertLess(self.wallet.balance, Decimal('5000.0000'))

        # Idempotent second callback
        bal_after = self.wallet.balance
        apply_payout_callback(event, provider_code='vimopay')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, bal_after)
        self.assertTrue(
            PayoutProviderEvent.objects.filter(
                merchant_ref_id=payout.transaction_id, direction='inbound'
            ).exists()
        )

    @patch('apps.fund_management.payout_orchestrator.resolve_payout_provider')
    @patch('apps.fund_management.payout_orchestrator.get_masters')
    @patch('apps.integrations.payout.beneficiary_location.lookup_ifsc_state', return_value='ANDHRA PRADESH')
    def test_process_payout_auto_resolves_state_from_ifsc(self, _mock_ifsc, mock_masters, mock_resolve):
        provider = self._mock_provider()
        mock_resolve.return_value = provider
        _bind_masters(mock_masters, provider)

        payout = process_payout(
            self.user,
            self.bank.id,
            Decimal('100'),
            transfer_mode='IMPS',
            beneficiary_location='',
        )
        self.assertEqual(payout.status, 'PENDING')
        self.assertEqual(payout.beneficiary_location, 'AP')
        initiate_req = provider.initiate.call_args.args[0]
        self.assertEqual(initiate_req.beneficiary_location, 'AP')

    @patch('apps.fund_management.payout_orchestrator.resolve_payout_provider')
    @patch('apps.fund_management.payout_orchestrator.get_masters')
    @patch('apps.integrations.payout.beneficiary_location.lookup_ifsc_state', return_value='')
    def test_callback_failed_releases_hold(self, _mock_ifsc, mock_masters, mock_resolve):
        provider = self._mock_provider()
        mock_resolve.return_value = provider
        _bind_masters(mock_masters, provider)

        payout = process_payout(
            self.user,
            self.bank.id,
            Decimal('100'),
            transfer_mode='IMPS',
            beneficiary_location='JH',
        )
        held = Wallet.objects.get(pk=self.wallet.pk).held_balance
        self.assertGreater(held, 0)

        apply_payout_callback(
            PayoutCallbackEvent(
                merchant_ref_id=payout.transaction_id,
                domain_status=DOMAIN_FAILED,
                provider_status_code='001',
                response_message='Invalid account',
                raw={},
            ),
            provider_code='vimopay',
        )
        payout.refresh_from_db()
        self.assertEqual(payout.status, 'FAILED')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.held_balance, Decimal('0.0000'))
        self.assertEqual(self.wallet.balance, Decimal('5000.0000'))

    def test_fail_closed_without_provider(self):
        ApiMaster.objects.filter(provider_type='payout').update(status='inactive', is_default=False)
        from apps.core.exceptions import TransactionFailed

        with self.assertRaises(TransactionFailed):
            process_payout(
                self.user,
                self.bank.id,
                Decimal('100'),
                transfer_mode='IMPS',
                beneficiary_location='JH',
            )


class VimopayUrlResolutionTests(TestCase):
    def _provider(self, *, base_url='https://prod.vidual.in', config_json=None):
        from apps.integrations.payout.providers.vimopay import VimopayPayoutProvider

        master = ApiMaster.objects.create(
            provider_code='vimopay',
            provider_name='VimoPay URL Test',
            provider_type='payout',
            base_url=base_url,
            status='sandbox',
            is_default=False,
            secrets_encrypted=encrypt_secret_payload(
                {
                    'secret_key': 'f37701ee0778cfe1dd97b7537ae71709',
                    'salt_key': 'bb13602c407b1ddd6506d59e410bafeb',
                    'encrypt_decrypt_key': '47cdba1911f078afe863774a8dffcb26',
                    'user_id': 'E5B82667-9A9D-4A5A-A55C-F3B1E10BF370',
                }
            ),
            config_json=config_json or {},
        )
        return VimopayPayoutProvider(master=master, secrets={
            'secret_key': 'f37701ee0778cfe1dd97b7537ae71709',
            'salt_key': 'bb13602c407b1ddd6506d59e410bafeb',
            'encrypt_decrypt_key': '47cdba1911f078afe863774a8dffcb26',
            'user_id': 'E5B82667-9A9D-4A5A-A55C-F3B1E10BF370',
        })

    def test_absolute_endpoints_used_as_is(self):
        provider = self._provider(
            config_json={
                'endpoints': {
                    'authorize': 'https://prod.vidual.in/payoutapi/api/Signature/Authorize',
                    'payout': 'https://prod.vidual.in/payoutapi/api/Payment/payout',
                    'bank_list': 'https://prod.vidual.in/masterapi/api/master/banklist',
                    'state_list': 'https://prod.vidual.in/masterapi/api/master/statelist',
                    'purpose_list': 'https://prod.vidual.in/masterapi/api/master/purposelist',
                }
            }
        )
        self.assertEqual(
            provider._url('authorize'),
            'https://prod.vidual.in/payoutapi/api/Signature/Authorize',
        )
        self.assertEqual(
            provider._url('payout'),
            'https://prod.vidual.in/payoutapi/api/Payment/payout',
        )
        self.assertNotIn('uat', provider._url('payout').lower())

    def test_relative_paths_join_base(self):
        provider = self._provider(
            config_json={'paths': {'payout': '/payoutapi/api/Payment/payout'}}
        )
        self.assertEqual(
            provider._url('payout'),
            'https://prod.vidual.in/payoutapi/api/Payment/payout',
        )

    def test_missing_falls_back_to_default_paths(self):
        from apps.integrations.payout.providers.vimopay import DEFAULT_PATHS

        provider = self._provider(config_json={})
        self.assertEqual(
            provider._url('payout'),
            f'https://prod.vidual.in{DEFAULT_PATHS["payout"]}',
        )

    @patch('apps.integrations.payout.providers.vimopay.requests.post')
    def test_authorize_hits_configured_url(self, mock_post):
        url = 'https://prod.vidual.in/payoutapi/api/Signature/Authorize'
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'successStatus': True,
            'responseCode': '000',
            'data': 'opaque-token-value',
        }
        mock_post.return_value = mock_resp
        provider = self._provider(config_json={'endpoints': {'authorize': url}})
        token = provider.authorize()
        self.assertEqual(token, 'opaque-token-value')
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.args[0], url)
