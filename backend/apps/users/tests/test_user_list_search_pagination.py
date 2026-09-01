"""User directory search is server-side and returns pagination metadata."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class UserListSearchPaginationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9112000001',
            email='list-admin@test.com',
            password='secret123',
            role='Admin',
            user_id='LSTADM1',
            first_name='Ada',
            last_name='Admin',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        for i in range(30):
            User.objects.create_user(
                phone=f'91120001{i:02d}',
                email=f'list-ret-{i}@test.com',
                password='secret123',
                role='Retailer',
                user_id=f'LSTR{i:02d}',
                first_name='Retail',
                last_name=f'User{i:02d}',
            )

    def test_search_and_pagination_params(self):
        res = self.client.get('/api/users/', {'search': 'User05', 'page': 1, 'page_size': 10})
        self.assertEqual(res.status_code, 200)
        data = res.data.get('data') or {}
        users = data.get('users') or []
        self.assertTrue(users)
        last_names = {u.get('last_name') for u in users}
        self.assertIn('User05', last_names)
        self.assertEqual(data.get('page'), 1)
        self.assertEqual(data.get('page_size'), 10)
        self.assertGreaterEqual(data.get('total') or 0, 1)

    def test_page_two_not_just_first_page(self):
        res = self.client.get('/api/users/', {'page': 2, 'page_size': 10, 'role': 'Retailer'})
        self.assertEqual(res.status_code, 200)
        data = res.data.get('data') or {}
        self.assertEqual(data.get('page'), 2)
        self.assertEqual(len(data.get('users') or []), 10)
        self.assertGreaterEqual(data.get('total') or 0, 30)
