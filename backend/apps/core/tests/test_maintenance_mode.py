"""Tests for system maintenance mode."""
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.core.maintenance_mode import (
    ACCESS_CODE_MODULE_MAINTENANCE,
    MODULE_PAY_IN,
    assert_module_available,
    get_status,
    invalidate_cache,
    is_module_enabled,
    update_config,
)
from apps.core.models import SystemMaintenanceConfig


class MaintenanceModeServiceTests(TestCase):
    def setUp(self):
        invalidate_cache()
        SystemMaintenanceConfig.objects.filter(pk=SystemMaintenanceConfig.SINGLETON_PK).delete()

    def test_defaults_all_enabled(self):
        self.assertTrue(is_module_enabled(MODULE_PAY_IN))
        status_data = get_status()
        self.assertTrue(status_data['pay_in']['enabled'])
        self.assertIn('maintenance', status_data['pay_in']['message'].lower())

    def test_disable_pay_in_raises(self):
        update_config(changed_by=None, patch={'pay_in_enabled': False})
        invalidate_cache()
        self.assertFalse(is_module_enabled(MODULE_PAY_IN))
        with self.assertRaises(PermissionDenied) as ctx:
            assert_module_available(MODULE_PAY_IN)
        detail = ctx.exception.detail
        self.assertEqual(detail['code'], ACCESS_CODE_MODULE_MAINTENANCE)
        self.assertEqual(detail['module'], MODULE_PAY_IN)

    def test_custom_user_message(self):
        update_config(
            changed_by=None,
            patch={
                'pay_in_enabled': False,
                'pay_in_message': 'Custom pay-in maintenance message.',
            },
        )
        invalidate_cache()
        status_data = get_status()
        self.assertEqual(status_data['pay_in']['message'], 'Custom pay-in maintenance message.')


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
)
class MaintenanceModeAPITests(TestCase):
    def setUp(self):
        invalidate_cache()
        SystemMaintenanceConfig.objects.filter(pk=SystemMaintenanceConfig.SINGLETON_PK).delete()
        self.admin = User.objects.create_user(
            phone='9000000001',
            email='admin-maint@test.com',
            password='testpass123',
            role='Admin',
            first_name='Admin',
            last_name='User',
            user_id='ADMMAINT1',
        )
        self.retailer = User.objects.create_user(
            phone='9000000002',
            email='retail-maint@test.com',
            password='testpass123',
            role='Retailer',
            first_name='Retail',
            last_name='User',
            user_id='RETLMAINT1',
        )
        self.client = APIClient()

    def test_admin_get_and_patch(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.get('/api/admin/maintenance/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['data']['maintenance']['pay_in']['enabled'])

        r2 = self.client.patch(
            '/api/admin/maintenance/',
            {'payout_enabled': False, 'reason_internal': 'Test outage'},
            format='json',
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertFalse(r2.data['data']['maintenance']['payout']['enabled'])
        self.assertEqual(r2.data['data']['maintenance']['reason_internal'], 'Test outage')

    def test_non_admin_cannot_patch(self):
        self.client.force_authenticate(user=self.retailer)
        r = self.client.patch('/api/admin/maintenance/', {'pay_in_enabled': False}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_status_endpoint(self):
        self.client.force_authenticate(user=self.retailer)
        r = self.client.get('/api/system/maintenance-status/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('pay_in', r.data['data']['maintenance'])
        self.assertNotIn('reason_internal', r.data['data']['maintenance'])

    def test_login_includes_maintenance(self):
        r = self.client.post(
            '/api/auth/login/',
            {'phone': '9000000002', 'password': 'testpass123'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('maintenance', r.data['data'])
