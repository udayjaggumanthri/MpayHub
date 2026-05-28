"""JWT and refresh-token access for disabled users with pay-in-only exception."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.authentication.services import create_jwt_tokens

User = get_user_model()


class PayInOnlyJwtAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555502',
            email='jwt-payin@test.com',
            password='secret123',
            role='Retailer',
            user_id='JWTPAY1',
        )
        self.user.is_active = False
        self.user.pay_in_allowed_when_disabled = True
        self.user.save(update_fields=['is_active', 'pay_in_allowed_when_disabled'])
        self.tokens = create_jwt_tokens(self.user)
        self.client = APIClient()

    def test_me_with_access_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.tokens["access"]}')
        r = self.client.get('/api/auth/me/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()['data']['user']['is_active'])
        self.assertTrue(r.json()['data']['user']['pay_in_allowed_when_disabled'])

    def test_wallets_with_access_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.tokens["access"]}')
        r = self.client.get('/api/wallets/')
        self.assertEqual(r.status_code, 200, r.content)

    def test_refresh_token_when_pay_in_allowed(self):
        r = self.client.post(
            '/api/auth/refresh-token/',
            {'refresh': self.tokens['refresh']},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('access', r.json()['data']['tokens'])

    def test_refresh_denied_when_fully_disabled(self):
        self.user.pay_in_allowed_when_disabled = False
        self.user.save(update_fields=['pay_in_allowed_when_disabled'])
        tokens = create_jwt_tokens(self.user)
        r = self.client.post(
            '/api/auth/refresh-token/',
            {'refresh': tokens['refresh']},
            format='json',
        )
        self.assertEqual(r.status_code, 401)
