from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class UserAccessControlsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9333333301',
            email='api-admin@test.com',
            password='secret123',
            role='Admin',
            user_id='APIADM1',
        )
        self.other_admin = User.objects.create_user(
            phone='9333333302',
            email='api-admin2@test.com',
            password='secret123',
            role='Admin',
            user_id='APIADM2',
        )
        self.retailer = User.objects.create_user(
            phone='9444444401',
            email='api-retailer@test.com',
            password='secret123',
            role='Retailer',
            user_id='APIRT1',
        )
        self.client = APIClient()

    def test_admin_can_set_restrict_and_lock(self):
        self.client.force_authenticate(user=self.admin)
        url = f'/api/users/{self.retailer.pk}/access-controls/'
        r = self.client.patch(
            url,
            {'is_restricted': True, 'payments_locked': True},
            format='json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body['success'])
        self.retailer.refresh_from_db()
        self.assertTrue(self.retailer.is_restricted)
        self.assertTrue(self.retailer.payments_locked)

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.retailer)
        url = f'/api/users/{self.retailer.pk}/access-controls/'
        r = self.client.patch(url, {'is_restricted': True}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_admin_cannot_disable_self(self):
        self.client.force_authenticate(user=self.admin)
        url = f'/api/users/{self.admin.pk}/access-controls/'
        r = self.client.patch(url, {'is_active': False}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('own account', r.json()['message'].lower())

    def test_cannot_disable_last_admin(self):
        self.other_admin.is_active = False
        self.other_admin.save(update_fields=['is_active'])
        self.client.force_authenticate(user=self.admin)
        url = f'/api/users/{self.admin.pk}/access-controls/'
        r = self.client.patch(url, {'is_active': False}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('last active administrator', r.json()['message'].lower())

    def test_disable_with_pay_in_allowed_when_disabled(self):
        self.client.force_authenticate(user=self.admin)
        url = f'/api/users/{self.retailer.pk}/access-controls/'
        r = self.client.patch(
            url,
            {'is_active': False, 'pay_in_allowed_when_disabled': True},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.retailer.refresh_from_db()
        self.assertFalse(self.retailer.is_active)
        self.assertTrue(self.retailer.pay_in_allowed_when_disabled)
