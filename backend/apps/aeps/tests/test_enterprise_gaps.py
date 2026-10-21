"""Tests for enterprise gaps: provider RBAC, OTP threshold, recon builders."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import ValidationError

from apps.aeps.services.config_audit import encrypted_profile_ready, mask_provider_row
from apps.aeps.services.gates import can_manage_aeps_provider
from apps.aeps.services.products import _otp_threshold, explain_provider_failure
from apps.aeps.services.recon import build_recon_items


User = get_user_model()


class ProviderReadyTests(SimpleTestCase):
    def test_simple_needs_password_and_secret(self):
        row = SimpleNamespace(
            environment='simple',
            api_mode='simple',
            resolved_api_mode='simple',
            super_merchant_id='1501',
            super_merchant_login_id='demo',
            secrets_encrypted='',
        )
        ok, msg = encrypted_profile_ready(row, {'password': 'x'})
        self.assertFalse(ok)
        self.assertIn('secret_key', msg)
        ok2, _ = encrypted_profile_ready(row, {'password': 'x', 'secret_key': 'sk'})
        self.assertTrue(ok2)

    def test_encrypted_needs_rsa(self):
        row = SimpleNamespace(
            environment='prod',
            api_mode='encrypted',
            resolved_api_mode='encrypted',
            super_merchant_id='1501',
            super_merchant_login_id='demo',
            secrets_encrypted='',
        )
        ok, msg = encrypted_profile_ready(
            row, {'password': 'x', 'secret_key': 'sk'}
        )
        self.assertFalse(ok)
        self.assertIn('RSA', msg)


class FaqMessageTests(SimpleTestCase):
    def test_fp097_message(self):
        msg = explain_provider_failure(
            {'status': False, 'message': 'Please complete bank eKYC to process'},
            {'kycResponseCode': 'FP097'},
        )
        self.assertIn('Bank eKYC', msg)
        self.assertIn('BeKYC', msg)


class OtpThresholdTests(SimpleTestCase):
    @patch('apps.aeps.models.AepsProviderConfig.objects')
    def test_default_threshold(self, mock_objects):
        mock_objects.filter.return_value.order_by.return_value.first.return_value = None
        self.assertEqual(_otp_threshold(), 5000)


class ReconBuilderTests(TestCase):
    def test_empty_day(self):
        items = build_recon_items(date(2099, 1, 1))
        self.assertEqual(items, [])


class ProviderGrantGateTests(TestCase):
    def test_super_admin_can_manage(self):
        user = User.objects.create_user(username='sa_aeps', password='x', role='Super Admin')
        self.assertTrue(can_manage_aeps_provider(user))

    def test_admin_without_grant_cannot(self):
        user = User.objects.create_user(username='adm_aeps', password='x', role='Admin')
        self.assertFalse(can_manage_aeps_provider(user))
