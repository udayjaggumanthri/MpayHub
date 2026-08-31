from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.aeps.models import AepsApiAuditLog, AepsProviderConfig
from apps.integrations.fingpay.client import FingpayClient
from apps.integrations.fingpay.endpoints import (
    SIMPLE_ENDPOINTS,
    default_endpoints_for,
    merge_endpoints,
)
from apps.integrations.fingpay.registry import _persist_audit, build_client_from_config
from apps.core.utils import encrypt_secret_payload


class EndpointMapTests(SimpleTestCase):
    def test_simple_defaults_use_v2_and_simple_paths(self):
        eps = default_endpoints_for(environment='simple')
        self.assertIn('/simple/', eps['onboarding_create_simple'])
        self.assertIn('/v2/', eps['cw'])
        self.assertIn('/simple/', eps['twofa_validate'])
        self.assertIn('/v1/', eps['ekyc_send_otp'])

    def test_encrypted_php_defaults(self):
        eps = default_endpoints_for(environment='prod', onboarding_api_style='php')
        self.assertIn('/php/', eps['cw'])
        self.assertIn('/php/', eps['twofa_validate'])

    def test_merge_overrides(self):
        merged = merge_endpoints(
            {'cw': 'custom/cw'},
            environment='prod',
            onboarding_api_style='php',
        )
        self.assertEqual(merged['cw'], 'custom/cw')
        self.assertTrue(merged['be'].endswith('getBalance'))


class ClientPathResolutionTests(SimpleTestCase):
    def test_simple_client_onboarding_url(self):
        client = FingpayClient(
            super_merchant_id='1501',
            super_merchant_login_id='login',
            password_plain='x',
            secret_key='sec',
            rsa_public_key_pem='',
            onboarding_base_url='https://fingpayap.tapits.in/fpaepsweb',
            ekyc_base_url='https://fpekyc.tapits.in',
            aeps_base_url='https://fingpayap.tapits.in',
            api_mode='simple',
            environment='simple',
            endpoints=SIMPLE_ENDPOINTS,
        )
        self.assertIn('/simple/creation/v2', client.onboarding_create_url())
        self.assertEqual(client.api_mode, 'simple')
        self.assertIn('/v2/withdrawal', client.product_path('CW'))

    def test_simple_ms_uses_production_host(self):
        client = FingpayClient(
            super_merchant_id='1501',
            super_merchant_login_id='login',
            password_plain='x',
            secret_key='sec',
            rsa_public_key_pem='',
            onboarding_base_url='https://fingpayap.tapits.in/fpaepsweb',
            ekyc_base_url='https://fpekyc.tapits.in',
            aeps_base_url='https://fingpayap.tapits.in',
            api_mode='simple',
            environment='simple',
            endpoints=SIMPLE_ENDPOINTS,
        )
        url = client._join(client.aeps_base_url, client.endpoint('ms'))
        self.assertEqual(
            url,
            'https://fingpayap.tapits.in/fpaepsservice/api/miniStatement/merchant/v2/statement',
        )
        self.assertTrue(url.endswith('/miniStatement/merchant/v2/statement'))


class ProviderConfigModelTests(TestCase):
    def test_simple_env_forces_simple_api_mode(self):
        row = AepsProviderConfig.objects.create(
            name='fingpay-simple-test',
            environment='simple',
            api_mode='encrypted',  # ignored when env=simple
            is_active=False,
        )
        self.assertEqual(row.resolved_api_mode, 'simple')
        self.assertEqual(row.resolved_onboarding_api_style, 'simple')
        self.assertIn('simple', row.onboarding_create_path())

    def test_activate_exclusivity_three_envs(self):
        uat = AepsProviderConfig.objects.create(name='fingpay-uat-t', environment='uat', is_active=True)
        prod = AepsProviderConfig.objects.create(name='fingpay-prod-t', environment='prod', is_active=False)
        simple = AepsProviderConfig.objects.create(name='fingpay-simple-t', environment='simple', is_active=False)
        AepsProviderConfig.objects.filter(is_deleted=False, is_active=True).update(is_active=False)
        simple.is_active = True
        simple.save()
        uat.refresh_from_db()
        prod.refresh_from_db()
        simple.refresh_from_db()
        self.assertFalse(uat.is_active)
        self.assertFalse(prod.is_active)
        self.assertTrue(simple.is_active)


class RegistryModeTests(TestCase):
    def test_simple_mode_builds_without_rsa(self):
        row = AepsProviderConfig.objects.create(
            name='fingpay-simple-reg',
            environment='simple',
            api_mode='simple',
            is_active=True,
            super_merchant_id='1501',
            super_merchant_login_id='MpLogin',
            onboarding_base_url='https://fpuat.tapits.in/fpaepsweb',
            ekyc_base_url='https://fpekyc.tapits.in',
            aeps_base_url='https://fpuat.tapits.in',
            secrets_encrypted=encrypt_secret_payload({'password': 'pass', 'secret_key': 'sek'}),
            egress_ip='139.99.47.143',
        )
        client = build_client_from_config(row)
        self.assertEqual(client.api_mode, 'simple')
        self.assertEqual(client.egress_ip, '139.99.47.143')
        self.assertEqual(client.secret_key, 'sek')

    def test_configured_egress_is_override_only_when_detection_fails(self):
        row = AepsProviderConfig.objects.create(
            name='fingpay-simple-egress',
            environment='simple',
            api_mode='simple',
            super_merchant_id='1501',
            super_merchant_login_id='MpLogin',
            onboarding_base_url='https://fingpayap.tapits.in/fpaepsweb',
            aeps_base_url='https://fingpayap.tapits.in',
            secrets_encrypted=encrypt_secret_payload({'password': 'pass', 'secret_key': 'sek'}),
            egress_ip='10.0.0.9',
        )
        with mock.patch(
            'apps.integrations.fingpay.netinfo.detect_outbound_ipv4', return_value='203.0.113.7'
        ):
            self.assertEqual(row.resolved_egress_ip(), '203.0.113.7')
        with mock.patch(
            'apps.integrations.fingpay.netinfo.detect_outbound_ipv4', return_value=''
        ):
            self.assertEqual(row.resolved_egress_ip(), '10.0.0.9')

    def test_encrypted_requires_rsa_or_bundled(self):
        row = AepsProviderConfig.objects.create(
            name='fingpay-enc-reg',
            environment='uat',
            api_mode='encrypted',
            is_active=True,
            super_merchant_id='1',
            super_merchant_login_id='u',
            onboarding_base_url='https://fpuat.tapits.in/fpaepsweb',
            ekyc_base_url='https://fpekyc.tapits.in',
            aeps_base_url='https://fpuat.tapits.in',
            secrets_encrypted=encrypt_secret_payload({'password': 'pass'}),
            onboarding_api_style='php',
        )
        client = build_client_from_config(row)
        self.assertEqual(client.api_mode, 'encrypted')
        self.assertTrue(client.rsa_public_key_pem)


class AuditDebugTests(TestCase):
    def test_debug_mode_stores_full_exchange(self):
        exchange = {
            'request': {'url': 'https://example/x', 'mode': 'simple_json', 'headers': {}, 'plain_json_scrubbed': {'a': 1}},
            'response': {'http_status': 200, 'latency_ms': 12, 'body': {'statusCode': 10000}},
            'diagnosis': 'ok',
            'share_with_tapits': {'request_headers': {'hash': 'abc'}, 'plain_json_request': {'a': 1}},
            'raw_request_body': {'a': 1, 'captureResponse': {'Piddata': 'secret'}},
            'raw_response_body': {'status': True, 'statusCode': 10000},
        }
        _persist_audit(
            endpoint='cw',
            method='POST',
            exchange=exchange,
            success=True,
            merchant_tran_id='T1',
            debug_mode=True,
        )
        row = AepsApiAuditLog.objects.get(merchant_tran_id='T1')
        self.assertTrue(row.debug_enabled)
        self.assertEqual(row.request_body.get('a'), 1)
        self.assertTrue(row.exchange_pack)

    def test_debug_off_skips_full_bodies(self):
        exchange = {
            'request': {'url': 'https://example/y', 'mode': 'x', 'headers': {}, 'plain_json_scrubbed': {}},
            'response': {'http_status': 200, 'latency_ms': 1, 'body': {'statusCode': '00'}},
            'raw_request_body': {'x': 1},
            'raw_response_body': {'y': 2},
            'share_with_tapits': {},
        }
        _persist_audit(
            endpoint='be',
            method='POST',
            exchange=exchange,
            success=True,
            merchant_tran_id='T2',
            debug_mode=False,
        )
        row = AepsApiAuditLog.objects.get(merchant_tran_id='T2')
        self.assertFalse(row.debug_enabled)
        self.assertEqual(row.request_body, {})
        self.assertEqual(row.exchange_pack, {})


class TwoFAPayloadContractTests(SimpleTestCase):
    """Ensure 2FA body uses AUO + serviceType per Fingpay TwoFA doc."""

    def test_complete_daily_2fa_payload_shape(self):
        # Inspect source constants / helper path without hitting DB heavily:
        from apps.aeps.services import products as products_svc
        import inspect

        src = inspect.getsource(products_svc.complete_daily_2fa)
        self.assertIn('twofa_validate', src)
        self.assertIn('include_body_timestamp=False', src)
        body_src = inspect.getsource(products_svc.twofa_request_body)
        self.assertIn("'transactionType': 'AUO'", body_src)
        self.assertIn("'serviceType':", body_src)
        self.assertNotIn("'timestamp'", body_src)
