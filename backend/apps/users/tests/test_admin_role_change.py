"""Admin role change — full promote/demote between Admin and Retailer."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.users.models import UserHierarchy
from apps.users.services import admin_change_user_role, create_user

User = get_user_model()


class AdminRoleChangeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9111111101',
            email='admin-role@test.com',
            password='pass123',
            role='Admin',
            user_id='LEGACYADMINROLE',
            member_number=901,
            member_id='MPH000901',
            display_code='A000901',
        )
        self.md, _ = create_user(
            {
                'phone': '9111111102',
                'email': 'md-role@test.com',
                'role': 'Master Distributor',
                'first_name': 'MD',
                'last_name': 'User',
            },
            self.admin,
        )
        self.retailer, _ = create_user(
            {
                'phone': '9111111103',
                'email': 'ret-role@test.com',
                'role': 'Retailer',
                'first_name': 'Ret',
                'last_name': 'User',
            },
            self.md,
        )

    def test_admin_promotes_retailer_under_md_to_super_distributor(self):
        """Parent onboarding rules must not block Admin manual role change."""
        updated = admin_change_user_role(
            actor=self.admin,
            target=self.retailer,
            new_role='Super Distributor',
        )
        self.assertEqual(updated.role, 'Super Distributor')

    def test_admin_promotes_retailer_to_admin(self):
        updated = admin_change_user_role(
            actor=self.admin,
            target=self.retailer,
            new_role='Admin',
        )
        self.assertEqual(updated.role, 'Admin')
        admin_change_user_role(actor=self.admin, target=updated, new_role='Retailer')

    def test_admin_cannot_demote_with_invalid_subordinates(self):
        distributor, _ = create_user(
            {
                'phone': '9111111104',
                'email': 'dist-role@test.com',
                'role': 'Distributor',
                'first_name': 'Dist',
                'last_name': 'User',
            },
            self.md,
        )
        UserHierarchy.objects.filter(child_user=distributor).delete()
        UserHierarchy.objects.create(parent_user=self.md, child_user=distributor)
        with self.assertRaises(ValueError) as ctx:
            admin_change_user_role(
                actor=self.admin,
                target=self.md,
                new_role='Retailer',
            )
        self.assertIn('subordinate', str(ctx.exception).lower())
