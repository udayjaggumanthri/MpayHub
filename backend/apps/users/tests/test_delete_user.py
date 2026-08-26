from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import UserHierarchy
from apps.users.services import delete_user_account

User = get_user_model()


class DeleteUserAccountTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9555555701',
            email='deladmin@test.com',
            password='secret123',
            role='Admin',
            user_id='DELADM1',
        )
        self.admin2 = User.objects.create_user(
            phone='9555555702',
            email='deladmin2@test.com',
            password='secret123',
            role='Admin',
            user_id='DELADM2',
        )
        self.retailer = User.objects.create_user(
            phone='9555555703',
            email='delret@test.com',
            password='secret123',
            role='Retailer',
            user_id='DELRT1',
        )
        self.distributor = User.objects.create_user(
            phone='9555555704',
            email='deldist@test.com',
            password='secret123',
            role='Distributor',
            user_id='DELDT1',
        )
        UserHierarchy.objects.create(parent_user=self.distributor, child_user=self.retailer)
        self.client = APIClient()

    def test_admin_can_delete_leaf_user(self):
        deleted_id = delete_user_account(actor=self.admin, target=self.retailer)
        self.assertEqual(deleted_id, 'DELRT1')
        self.assertFalse(User.objects.filter(pk=self.retailer.pk).exists())

    def test_cannot_delete_user_with_subordinates(self):
        with self.assertRaises(ValueError) as ctx:
            delete_user_account(actor=self.admin, target=self.distributor)
        self.assertIn('subordinates', str(ctx.exception).lower())

    def test_cannot_delete_self(self):
        with self.assertRaises(ValueError):
            delete_user_account(actor=self.admin, target=self.admin)

    def test_cannot_delete_last_admin(self):
        self.admin2.delete()
        with self.assertRaises(ValueError):
            delete_user_account(actor=self.admin, target=self.admin)

    def test_delete_api_admin_only(self):
        self.client.force_authenticate(user=self.retailer)
        resp = self.client.delete(f'/api/users/{self.distributor.pk}/')
        self.assertEqual(resp.status_code, 403)

    def test_delete_api_success(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f'/api/users/{self.retailer.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get('success'))
        self.assertFalse(User.objects.filter(pk=self.retailer.pk).exists())

    def test_admin_can_delete_user_with_aeps_transactions(self):
        from apps.aeps.models import AepsTransaction

        AepsTransaction.objects.create(
            user=self.retailer,
            merchant_tran_id='MSDELTEST0001',
            product='MS',
            status='failed',
        )
        deleted_id = delete_user_account(actor=self.admin, target=self.retailer)
        self.assertEqual(deleted_id, 'DELRT1')
        self.assertFalse(User.objects.filter(pk=self.retailer.pk).exists())
        self.assertFalse(AepsTransaction.objects.filter(merchant_tran_id='MSDELTEST0001').exists())
