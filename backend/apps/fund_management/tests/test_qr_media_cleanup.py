"""QR account media cleanup on soft-delete and image replace."""
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from apps.fund_management.models import PayInQrAccount

User = get_user_model()


def _png(color=(10, 20, 30)):
    buf = BytesIO()
    Image.new('RGB', (32, 32), color=color).save(buf, format='PNG')
    return SimpleUploadedFile('qr.png', buf.getvalue(), content_type='image/png')


class PayInQrAccountMediaCleanupTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9000000099',
            email='qr-cleanup-admin@example.com',
            password='TestPass123!',
            role='Admin',
            user_id='QRCLN1',
            first_name='Admin',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _create_qr(self, *, color=(10, 20, 30)):
        return PayInQrAccount.objects.create(
            display_name='Cleanup QR',
            account_display_name='Acct',
            upi_vpa='cleanup@upi',
            qr_image=_png(color),
            status='active',
            daily_limit_24h=Decimal('10000'),
            max_per_txn=Decimal('5000'),
            charge_rate=Decimal('0'),
        )

    def test_destroy_soft_deletes_and_removes_storage_object(self):
        qr = self._create_qr()
        name = qr.qr_image.name
        self.assertTrue(default_storage.exists(name))

        resp = self.client.delete(f'/api/admin/pay-in-qr-accounts/{qr.pk}/')
        self.assertEqual(resp.status_code, 200, resp.content)

        qr.refresh_from_db()
        self.assertTrue(qr.is_deleted)
        self.assertFalse(bool(qr.qr_image))
        self.assertFalse(default_storage.exists(name))

    def test_update_replaces_image_and_deletes_old_storage_object(self):
        qr = self._create_qr(color=(1, 2, 3))
        old_name = qr.qr_image.name
        self.assertTrue(default_storage.exists(old_name))

        resp = self.client.patch(
            f'/api/admin/pay-in-qr-accounts/{qr.pk}/',
            {'qr_image': _png(color=(200, 100, 50))},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 200, resp.content)

        qr.refresh_from_db()
        new_name = qr.qr_image.name
        self.assertTrue(new_name)
        self.assertNotEqual(old_name, new_name)
        self.assertTrue(default_storage.exists(new_name))
        self.assertFalse(default_storage.exists(old_name))
