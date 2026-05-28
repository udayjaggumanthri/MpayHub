from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import UserHierarchy

User = get_user_model()


class UserDetailProfileAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            phone='9111111101',
            email='prof-admin@test.com',
            password='secret123',
            role='Admin',
            user_id='PRADM1',
        )
        self.distributor = User.objects.create_user(
            phone='9222222201',
            email='prof-dist@test.com',
            password='secret123',
            role='Distributor',
            user_id='PRDT1',
        )
        self.retailer = User.objects.create_user(
            phone='9333333301',
            email='prof-retailer@test.com',
            password='secret123',
            role='Retailer',
            user_id='PRRT1',
        )
        UserHierarchy.objects.create(parent_user=self.distributor, child_user=self.retailer)

    def _user_detail(self, actor, target_pk):
        self.client.force_authenticate(user=actor)
        return self.client.get(f'/api/users/{target_pk}/')

    def _user_from_detail_response(self, response):
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        data = body.get('data', body)
        if isinstance(data, dict) and 'user' in data:
            return data['user']
        return data

    def test_admin_sees_full_hierarchy_not_point_of_contact(self):
        r = self._user_detail(self.admin, self.retailer.pk)
        user = self._user_from_detail_response(r)
        self.assertIsNotNone(user.get('hierarchy_lineage'))
        self.assertIn('map_path', user['hierarchy_lineage'])
        self.assertIsNone(user.get('point_of_contact'))

    def test_non_admin_sees_point_of_contact_not_full_hierarchy(self):
        r = self._user_detail(self.distributor, self.retailer.pk)
        user = self._user_from_detail_response(r)
        self.assertIsNone(user.get('hierarchy_lineage'))
        poc = user.get('point_of_contact')
        self.assertIsNotNone(poc)
        self.assertEqual(len(poc['contacts']), 1)
        contact = poc['contacts'][0]
        self.assertEqual(contact['user_id'], self.distributor.user_id)
        self.assertEqual(contact['role'], 'Distributor')
        self.assertEqual(contact['id'], self.distributor.pk)

    def test_non_admin_can_retrieve_subordinate_and_self(self):
        """PoC links and own profile must not 404."""
        for target in (self.retailer.pk, self.distributor.pk):
            r = self._user_detail(self.distributor, target)
            self.assertEqual(r.status_code, 200, r.content)

    def test_non_admin_cannot_fetch_user_packages(self):
        self.client.force_authenticate(user=self.distributor)
        r = self.client.get(f'/api/fund-management/packages/user/{self.retailer.pk}/')
        self.assertEqual(r.status_code, 403)
