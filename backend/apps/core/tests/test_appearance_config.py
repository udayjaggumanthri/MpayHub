"""Tests for platform appearance configuration."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.core.appearance import (
    DEFAULT_LOGIN_TAGLINE,
    DEFAULT_LOGIN_WELCOME_HEADING,
    DEFAULT_SITE_TITLE,
    get_status,
    invalidate_cache,
    update_config,
)
from apps.core.models import PlatformAppearanceConfig


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
)
class AppearanceConfigServiceTests(TestCase):
    def setUp(self):
        invalidate_cache()
        PlatformAppearanceConfig.objects.filter(pk=PlatformAppearanceConfig.SINGLETON_PK).delete()

    def test_defaults_on_first_access(self):
        status_data = get_status()
        self.assertEqual(status_data['site_title'], DEFAULT_SITE_TITLE)
        self.assertEqual(status_data['login_welcome_heading'], DEFAULT_LOGIN_WELCOME_HEADING)
        self.assertEqual(status_data['login_tagline'], DEFAULT_LOGIN_TAGLINE)
        self.assertEqual(status_data['default_theme'], 'light')
        self.assertFalse(status_data['user_theme_toggle_enabled'])
        self.assertIsNone(status_data['logo_url'])

    def test_update_site_title(self):
        update_config(changed_by=None, patch={'site_title': 'Custom Title'})
        invalidate_cache()
        self.assertEqual(get_status()['site_title'], 'Custom Title')

    def test_update_theme_settings(self):
        update_config(
            changed_by=None,
            patch={'default_theme': 'dark', 'user_theme_toggle_enabled': True},
        )
        invalidate_cache()
        data = get_status()
        self.assertEqual(data['default_theme'], 'dark')
        self.assertTrue(data['user_theme_toggle_enabled'])


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
)
class AppearanceConfigAPITests(TestCase):
    def setUp(self):
        invalidate_cache()
        PlatformAppearanceConfig.objects.filter(pk=PlatformAppearanceConfig.SINGLETON_PK).delete()
        self.client = APIClient()
        self.admin = User.objects.create_user(
            phone='9000000101',
            email='admin-appearance@test.com',
            password='testpass123',
            role='Admin',
            first_name='Admin',
            last_name='User',
            user_id='ADMAPPEAR1',
        )
        self.retailer = User.objects.create_user(
            phone='9000000102',
            email='retail-appearance@test.com',
            password='testpass123',
            role='Retailer',
            first_name='Retail',
            last_name='User',
            user_id='RTLAPPEAR1',
        )

    def test_public_get_without_auth(self):
        r = self.client.get('/api/system/appearance/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['success'])
        self.assertEqual(r.data['data']['appearance']['site_title'], DEFAULT_SITE_TITLE)

    def test_admin_get_requires_admin(self):
        self.client.force_authenticate(user=self.retailer)
        r = self.client.get('/api/admin/appearance/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_patch_requires_admin(self):
        self.client.force_authenticate(user=self.retailer)
        r = self.client.patch('/api/admin/appearance/', {'site_title': 'Hacked'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_patch(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.patch(
            '/api/admin/appearance/',
            {'site_title': 'Admin Title', 'default_theme': 'dark'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['data']['appearance']['site_title'], 'Admin Title')
        self.assertEqual(r.data['data']['appearance']['default_theme'], 'dark')

    def test_rejects_invalid_image_type(self):
        self.client.force_authenticate(user=self.admin)
        bad = SimpleUploadedFile('test.txt', b'not an image', content_type='text/plain')
        r = self.client.patch('/api/admin/appearance/', {'logo': bad}, format='multipart')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
