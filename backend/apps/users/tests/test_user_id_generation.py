"""Legacy generate_user_id helper tests (deprecated allocator still unit-tested)."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.utils import generate_user_id

User = get_user_model()


class GenerateUserIdTests(TestCase):
    """Deprecated helper — kept for transitional tooling / historical format knowledge."""

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
