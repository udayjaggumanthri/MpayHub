from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class LoginAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone='9555555501',
            email='login-access@test.com',
            password='secret123',
            role='Retailer',
            user_id='LOGACC1',
        )

    def test_disabled_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        r = self.client.post(
            '/api/auth/login/',
            {'phone': self.user.phone, 'password': 'secret123'},
            format='json',
        )
        self.assertEqual(r.status_code, 400)

    def test_disabled_user_with_pay_in_flag_can_login(self):
        self.user.is_active = False
        self.user.pay_in_allowed_when_disabled = True
        self.user.save(update_fields=['is_active', 'pay_in_allowed_when_disabled'])
        r = self.client.post(
            '/api/auth/login/',
            {'phone': self.user.phone, 'password': 'secret123'},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json().get('success'))
