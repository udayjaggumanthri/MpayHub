"""Tests for sequential user_id allocation."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.utils import generate_user_id
from apps.users.models import UserHierarchy
from apps.users.services import create_user

User = get_user_model()


class GenerateUserIdTests(TestCase):
    def test_next_id_uses_all_rows_with_prefix_not_role_filter(self):
        User.objects.create_user(
            phone='9111111101',
            email='sd3_retailer@test.com',
            password='pass123',
            role='Retailer',
            user_id='SD3',
            first_name='Legacy',
            last_name='SD',
        )
        User.objects.create_user(
            phone='9111111102',
            email='sd1@test.com',
            password='pass123',
            role='Super Distributor',
            user_id='SD1',
        )
        User.objects.create_user(
            phone='9111111103',
            email='sd2@test.com',
            password='pass123',
            role='Super Distributor',
            user_id='SD2',
        )

        self.assertEqual(generate_user_id('Super Distributor'), 'SD4')

    def test_retailer_skips_ids_held_by_other_roles(self):
        User.objects.create_user(
            phone='9222222201',
            email='r7_dist@test.com',
            password='pass123',
            role='Distributor',
            user_id='R7',
            first_name='Was',
            last_name='Retailer',
        )
        User.objects.create_user(
            phone='9222222202',
            email='r1@test.com',
            password='pass123',
            role='Retailer',
            user_id='R1',
        )

        self.assertEqual(generate_user_id('Retailer'), 'R8')

    def test_explicit_existing_list_still_supported(self):
        self.assertEqual(generate_user_id('Distributor', ['DT1', 'DT3']), 'DT4')


class CreateUserUserIdTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9333333301',
            email='createuid_admin@test.com',
            password='pass123',
            role='Admin',
            user_id='ADMIN9001',
        )

    def test_create_super_distributor_after_role_changed_sd_id(self):
        holder = User.objects.create_user(
            phone='9333333302',
            email='sd3_holder@test.com',
            password='pass123',
            role='Retailer',
            user_id='SD3',
        )
        User.objects.create_user(
            phone='9333333303',
            email='sd1_holder@test.com',
            password='pass123',
            role='Super Distributor',
            user_id='SD1',
        )
        User.objects.create_user(
            phone='9333333304',
            email='sd2_holder@test.com',
            password='pass123',
            role='Super Distributor',
            user_id='SD2',
        )
        self.assertEqual(holder.role, 'Retailer')
        self.assertEqual(holder.user_id, 'SD3')

        user, _temp = create_user(
            {
                'phone': '9333333305',
                'email': 'new_sd@test.com',
                'role': 'Super Distributor',
                'first_name': 'New',
                'last_name': 'SD',
            },
            self.admin,
        )
        self.assertEqual(user.user_id, 'SD4')
        self.assertTrue(UserHierarchy.objects.filter(parent_user=self.admin, child_user=user).exists())

    def test_create_retailer_after_role_changed_r_id(self):
        User.objects.create_user(
            phone='9444444401',
            email='r7_holder@test.com',
            password='pass123',
            role='Distributor',
            user_id='R7',
        )
        user, _temp = create_user(
            {
                'phone': '9444444402',
                'email': 'new_r@test.com',
                'role': 'Retailer',
                'first_name': 'New',
                'last_name': 'R',
            },
            self.admin,
        )
        self.assertEqual(user.user_id, 'R8')
