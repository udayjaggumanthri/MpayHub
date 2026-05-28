from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.users.models import UserHierarchy
from apps.users.services import create_user

User = get_user_model()


class CreateUserPasswordOnboardingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9333333399',
            email='create-pwd-admin@test.com',
            password='adminpass1',
            role='Admin',
            user_id='CRPADM1',
        )

    def test_create_without_password_issues_unique_temp_and_flag(self):
        user_data = {
            'phone': '9444444499',
            'email': 'create-pwd-user@test.com',
            'role': 'Retailer',
            'first_name': 'Test',
            'last_name': 'User',
        }
        user, temp = create_user(user_data, self.admin)
        self.assertIsNotNone(temp)
        self.assertNotEqual(temp, 'default123')
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.check_password(temp))
        self.assertTrue(UserHierarchy.objects.filter(parent_user=self.admin, child_user=user).exists())

    def test_create_with_password_skips_forced_reset(self):
        user_data = {
            'phone': '9555555599',
            'email': 'create-pwd-custom@test.com',
            'role': 'Retailer',
            'first_name': 'Custom',
            'last_name': 'Pass',
            'password': 'CustomPass99',
        }
        user, temp = create_user(user_data, self.admin)
        self.assertIsNone(temp)
        self.assertFalse(user.must_change_password)
        self.assertTrue(user.check_password('CustomPass99'))
