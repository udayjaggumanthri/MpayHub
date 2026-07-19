"""
Tests for MSG91 Flow adapter, variable remapping, and SMS dispatch gates.
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.notifications.models import SmsDeliveryLog, SmsNotificationTemplate, SmsProviderConfig
from apps.notifications.providers.msg91 import Msg91Adapter, extract_msg91_vars, suggest_variable_map
from apps.notifications.services.dispatch import SmsNotificationService
from apps.notifications.services.variable_map import apply_variable_map

User = get_user_model()


class VariableMapTests(TestCase):
    def test_empty_map_passthrough(self):
        out = apply_variable_map({'otp': '123456', 'name': 'Uday'}, {})
        self.assertEqual(out, {'otp': '123456', 'name': 'Uday'})

    def test_remap_to_var_keys(self):
        out = apply_variable_map(
            {'otp': '123456', 'expiry_minutes': '10', 'extra': 'x'},
            {'otp': 'var1', 'expiry_minutes': 'var2'},
        )
        self.assertEqual(out, {'var1': '123456', 'var2': '10'})
        self.assertNotIn('extra', out)

    def test_remap_to_named_keys(self):
        out = apply_variable_map(
            {'amount': '100.00', 'transaction_id': 'LM1', 'reference': 'x'},
            {'amount': 'amount', 'transaction_id': 'transaction_id'},
        )
        self.assertEqual(out, {'amount': '100.00', 'transaction_id': 'LM1'})


class Msg91AdapterHelpersTests(TestCase):
    def test_extract_vars_from_template_body(self):
        body = 'Dear ##var1##, amount ##VAR2## thanks ##var1##'
        self.assertEqual(extract_msg91_vars(body), ['var1', 'var2'])

    def test_extract_named_flow_placeholders(self):
        body = (
            'Hi, Your MPAYHUB Wallet has been credited with Rs. ##amount## '
            'via Txn ID: ##transaction_id##. Thank you!'
        )
        self.assertEqual(extract_msg91_vars(body), ['amount', 'transaction_id'])

    def test_extract_dlt_style_var_placeholders(self):
        body = (
            'Dear {#var#},\n\n'
            'Your OTP for MPAYHUB verification is {#var#}.\n\n'
            'This OTP is valid for 10 minutes.'
        )
        self.assertEqual(extract_msg91_vars(body), ['var1', 'var2'])

    def test_suggest_variable_map_prefers_name_match(self):
        schema = [
            {'name': 'amount'},
            {'name': 'transaction_id'},
            {'name': 'reference'},
        ]
        suggested = suggest_variable_map(schema, ['amount', 'transaction_id'])
        self.assertEqual(
            suggested,
            {'amount': 'amount', 'transaction_id': 'transaction_id'},
        )

    def test_suggest_variable_map_positional_varn(self):
        schema = [{'name': 'name'}, {'name': 'otp'}]
        suggested = suggest_variable_map(schema, ['var1', 'var2'])
        self.assertEqual(suggested, {'name': 'var1', 'otp': 'var2'})

    def test_suggest_complaint_varn_template(self):
        schema = [
            {'name': 'txn_ref', 'required': True},
            {'name': 'complaint_id', 'required': True},
        ]
        suggested = suggest_variable_map(schema, ['var1', 'var2'])
        self.assertEqual(suggested, {'txn_ref': 'var1', 'complaint_id': 'var2'})

    def test_build_sync_result_named_payin(self):
        from apps.notifications.services.template_sync import build_sync_result

        body = (
            'Hi, Your MPAYHUB Wallet has been credited with Rs. ##amount## '
            'via Txn ID: ##transaction_id##. Thank you!'
        )
        result = build_sync_result(
            schema=[
                {'name': 'amount', 'required': True},
                {'name': 'transaction_id', 'required': True},
            ],
            template_body=body,
        )
        self.assertEqual(result.detected_vars, ['amount', 'transaction_id'])
        self.assertEqual(
            result.variable_map,
            {'amount': 'amount', 'transaction_id': 'transaction_id'},
        )
        self.assertEqual(result.unmapped_required, [])

    @patch('apps.notifications.providers.msg91.requests.post')
    def test_send_template_flow_payload(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.content = b'{"message":"req123","type":"success"}'
        mock_resp.json.return_value = {'message': 'req123', 'type': 'success'}
        mock_post.return_value = mock_resp

        adapter = Msg91Adapter(auth_key='test-key', api_base_url='https://control.msg91.com')
        result = adapter.send_template(
            '919876543210',
            'tmpl123',
            {'amount': '500.00', 'transaction_id': 'LM99'},
            sender_id='MPAYHB',
        )
        self.assertTrue(result.success)
        self.assertEqual(result.message_id, 'req123')
        args, kwargs = mock_post.call_args
        self.assertTrue(str(args[0]).endswith('/api/v5/flow/'))
        self.assertEqual(kwargs['headers']['authkey'], 'test-key')
        body = kwargs['json']
        self.assertEqual(body['template_id'], 'tmpl123')
        self.assertEqual(body['recipients'][0]['mobiles'], '919876543210')
        self.assertEqual(body['recipients'][0]['amount'], '500.00')
        self.assertEqual(body['recipients'][0]['transaction_id'], 'LM99')
        self.assertEqual(body['sender'], 'MPAYHB')

    @patch('apps.notifications.providers.msg91.requests.post')
    def test_get_template_versions(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.content = b'{}'
        mock_resp.json.return_value = {
            'data': [
                {
                    'id': '1',
                    'template_id': '6a4503e82abed18d7607c632',
                    'template_name': 'User_Registration',
                    'template_data': 'Dear ##var1##, Welcome to MPAYHUB!',
                    'DLT_ID': '1007165158208125858',
                    'sender_id': 'MPAYHB',
                    'version': 'v1.0',
                    'status': '1',
                    'active_status': '1',
                }
            ],
            'status': 'success',
            'hasError': False,
            'errors': [],
        }
        mock_post.return_value = mock_resp

        adapter = Msg91Adapter(auth_key='test-key')
        result = adapter.get_template_versions('6a4503e82abed18d7607c632')
        self.assertTrue(result['success'])
        self.assertEqual(result['primary']['template_name'], 'User_Registration')
        self.assertEqual(result['primary']['detected_vars'], ['var1'])
        self.assertTrue(str(mock_post.call_args[0][0]).endswith('/api/v5/sms/getTemplateVersions'))

    @patch('apps.notifications.providers.msg91.requests.post')
    def test_get_template_versions_named_vars(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.content = b'{}'
        mock_resp.json.return_value = {
            'data': [
                {
                    'id': '1',
                    'template_id': '6a5ccf01ca39642e200cdd52',
                    'template_name': 'PayIn_Successful',
                    'template_data': (
                        'Hi, Your MPAYHUB Wallet has been credited with Rs. ##amount## '
                        'via Txn ID: ##transaction_id##. Thank you!'
                    ),
                    'DLT_ID': '1007844631895457842',
                    'sender_id': 'MPAYHB',
                }
            ],
            'hasError': False,
        }
        mock_post.return_value = mock_resp
        adapter = Msg91Adapter(auth_key='test-key')
        result = adapter.get_template_versions('6a5ccf01ca39642e200cdd52')
        self.assertEqual(result['primary']['detected_vars'], ['amount', 'transaction_id'])
        suggested = suggest_variable_map(
            [{'name': 'amount'}, {'name': 'transaction_id'}],
            result['primary']['detected_vars'],
        )
        self.assertEqual(suggested, {'amount': 'amount', 'transaction_id': 'transaction_id'})


@override_settings(DEBUG=False)
class SmsDispatchRemapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9876543210',
            email='sms@test.com',
            password='secret123',
            role='Retailer',
            user_id='SMSTST1',
        )
        self.cfg = SmsProviderConfig.objects.create(
            name='msg91-test',
            provider='msg91',
            enabled=True,
            is_active=True,
            sender_id='MPAYHB',
            country_code='91',
        )
        self.cfg.set_auth_key('fake-auth-key')
        self.cfg.save()
        self.tpl = SmsNotificationTemplate.objects.create(
            event_key='onboarding.welcome',
            module='onboarding',
            label='User Registration',
            is_enabled=True,
            template_id='tmpl-welcome',
            variable_schema=[
                {'name': 'name', 'required': True},
                {'name': 'user_id', 'required': True},
            ],
            sample_variables={'name': 'Retailer', 'user_id': 'RTL001'},
            variable_map={'name': 'var1', 'user_id': 'var2'},
        )

    @patch('apps.notifications.providers.msg91.Msg91Adapter.send_template')
    def test_dispatch_applies_variable_map(self, mock_send):
        from apps.notifications.providers.base import SendResult

        mock_send.return_value = SendResult(success=True, message_id='mid-1')
        result = SmsNotificationService.dispatch(
            'onboarding.welcome',
            self.user.phone,
            {'name': 'Uday', 'user_id': 'SMSTST1'},
            user_id=self.user.pk,
            idempotency_key='test:welcome:1',
        )
        self.assertEqual(result['status'], 'sent')
        kwargs = mock_send.call_args
        # positional: phone, template_id, variables
        variables = kwargs[0][2]
        self.assertEqual(variables, {'var1': 'Uday', 'var2': 'SMSTST1'})
        log = SmsDeliveryLog.objects.get(idempotency_key='test:welcome:1')
        self.assertEqual(log.status, 'sent')

    @patch('apps.notifications.providers.msg91.Msg91Adapter.send_template')
    def test_dispatch_named_payin_map(self, mock_send):
        from apps.notifications.providers.base import SendResult

        SmsNotificationTemplate.objects.create(
            event_key='payin.success',
            module='payin',
            label='Pay-in Successful',
            is_enabled=True,
            template_id='tmpl-payin',
            variable_schema=[
                {'name': 'amount', 'required': True},
                {'name': 'transaction_id', 'required': True},
            ],
            sample_variables={'amount': '10.00', 'transaction_id': 'LM1'},
            variable_map={'amount': 'amount', 'transaction_id': 'transaction_id'},
        )
        mock_send.return_value = SendResult(success=True, message_id='mid-2')
        result = SmsNotificationService.dispatch(
            'payin.success',
            self.user.phone,
            {'amount': '250.50', 'transaction_id': 'LM999'},
            user_id=self.user.pk,
            idempotency_key='test:payin:1',
        )
        self.assertEqual(result['status'], 'sent')
        variables = mock_send.call_args[0][2]
        self.assertEqual(variables, {'amount': '250.50', 'transaction_id': 'LM999'})

    def test_dispatch_skips_when_event_disabled(self):
        self.tpl.is_enabled = False
        self.tpl.save(update_fields=['is_enabled'])
        result = SmsNotificationService.dispatch(
            'onboarding.welcome',
            self.user.phone,
            {'name': 'Uday', 'user_id': 'SMSTST1'},
            user_id=self.user.pk,
            idempotency_key='test:welcome:disabled',
        )
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['skip_reason'], 'event_disabled')

    def test_dispatch_skips_when_profile_disabled(self):
        self.cfg.enabled = False
        self.cfg.save(update_fields=['enabled'])
        result = SmsNotificationService.dispatch(
            'onboarding.welcome',
            self.user.phone,
            {'name': 'Uday', 'user_id': 'SMSTST1'},
            user_id=self.user.pk,
            idempotency_key='test:welcome:global',
        )
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['skip_reason'], 'global_disabled')
