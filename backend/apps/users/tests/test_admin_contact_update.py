from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory

from apps.users.serializers import UserUpdateSerializer

User = get_user_model()


class AdminContactUpdateApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9333333311',
            email='contact-admin@test.com',
            password='secret123',
            role='Admin',
            user_id='CTCADM1',
        )
        self.retailer = User.objects.create_user(
            phone='9444444411',
            email='contact-retailer@test.com',
            password='secret123',
            role='Retailer',
            user_id='CTCRT1',
        )
        self.other = User.objects.create_user(
            phone='9555555511',
            email='contact-other@test.com',
            password='secret123',
            role='Retailer',
            user_id='CTCRT2',
        )
        self.client = APIClient()

    def _url(self, user_pk):
        return f'/api/users/{user_pk}/contact/'

    def test_admin_can_update_contact_for_another_user(self):
        self.client.force_authenticate(user=self.admin)
        payload = {'email': 'new-retailer@test.com', 'phone': '9666666611'}
        r = self.client.patch(self._url(self.retailer.pk), payload, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body['success'])
        self.retailer.refresh_from_db()
        self.assertEqual(self.retailer.email, payload['email'])
        self.assertEqual(self.retailer.phone, payload['phone'])

    def test_duplicate_phone_rejected(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.patch(
            self._url(self.retailer.pk),
            {'email': 'unique@test.com', 'phone': self.other.phone},
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('phone', r.json()['errors'])

    def test_duplicate_email_rejected(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.patch(
            self._url(self.retailer.pk),
            {'email': self.other.email, 'phone': '9777777711'},
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('email', r.json()['errors'])

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.retailer)
        r = self.client.patch(
            self._url(self.other.pk),
            {'email': 'x@test.com', 'phone': '9888888811'},
            format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_admin_cannot_edit_self(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.patch(
            self._url(self.admin.pk),
            {'email': 'self-new@test.com', 'phone': '9999999911'},
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('own contact', r.json()['message'].lower())

    def test_invalid_phone_format_rejected(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.patch(
            self._url(self.retailer.pk),
            {'email': 'ok@test.com', 'phone': '12345'},
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('phone', r.json()['errors'])

    def test_non_admin_cannot_change_email_via_user_update_serializer(self):
        factory = APIRequestFactory()
        request = factory.patch('/')
        request.user = self.retailer
        serializer = UserUpdateSerializer(
            instance=self.retailer,
            data={'email': 'hijack@test.com'},
            partial=True,
            context={'request': request},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)
