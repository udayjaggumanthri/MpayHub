from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.users.hierarchy_policy import (
    can_parent_create_child,
    creatable_roles_for,
    policy_snapshot,
)
from apps.users.models import UserHierarchy
from apps.users.services import create_user

User = get_user_model()


class HierarchyPolicyTests(TestCase):
    def test_admin_creatable_roles(self):
        roles = creatable_roles_for('Admin')
        self.assertEqual(
            roles,
            ['Super Distributor', 'Master Distributor', 'Distributor', 'Retailer'],
        )

    def test_super_distributor_creatable_roles(self):
        roles = creatable_roles_for('Super Distributor')
        self.assertEqual(roles, ['Master Distributor', 'Distributor', 'Retailer'])

    def test_master_distributor_creatable_roles(self):
        roles = creatable_roles_for('Master Distributor')
        self.assertEqual(roles, ['Distributor', 'Retailer'])

    def test_distributor_creatable_roles(self):
        roles = creatable_roles_for('Distributor')
        self.assertEqual(roles, ['Retailer'])

    def test_retailer_cannot_create(self):
        self.assertEqual(creatable_roles_for('Retailer'), [])
        self.assertFalse(can_parent_create_child('Retailer', 'Retailer'))

    def test_user_hierarchy_delegates_to_policy(self):
        self.assertTrue(
            UserHierarchy.can_parent_role_create_child_role('Super Distributor', 'Master Distributor')
        )
        self.assertFalse(
            UserHierarchy.can_parent_role_create_child_role('Master Distributor', 'Super Distributor')
        )

    def test_policy_snapshot_keys(self):
        snapshot = policy_snapshot()
        self.assertIn('Super Distributor', snapshot)
        self.assertIn('Master Distributor', snapshot['Super Distributor'])


class SuperDistributorCreateMasterDistributorTests(TestCase):
    def setUp(self):
        self.sd = User.objects.create_user(
            phone='9444444401',
            email='sd_create_md@test.com',
            password='testpass123',
            role='Super Distributor',
            user_id='SDCRT1',
            first_name='Super',
            last_name='Dist',
        )

    def test_sd_can_create_master_distributor(self):
        user, _temp = create_user(
            {
                'phone': '9444444402',
                'email': 'md_create@test.com',
                'role': 'Master Distributor',
                'first_name': 'Master',
                'last_name': 'Dist',
            },
            self.sd,
        )
        self.assertEqual(user.role, 'Master Distributor')
        self.assertTrue(
            UserHierarchy.objects.filter(parent_user=self.sd, child_user=user).exists()
        )
