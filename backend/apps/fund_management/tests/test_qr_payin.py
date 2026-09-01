"""Manual QR pay-in: checkout merge, submit, limits, approve/reject."""
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.exceptions import ValidationError

from apps.contacts.models import Contact
from apps.fund_management.checkout_options import list_payin_checkout_options_for_user
from apps.fund_management.models import LoadMoney, PayInPackage, PayInQrAccount, UserPackageAssignment
from apps.fund_management.package_qr_accounts import sync_package_qr_links
from apps.fund_management.qr_approval import approve_qr_payin, reject_qr_payin, release_qr_utr
from apps.fund_management.services_qr import submit_qr_payin, utr_exists

User = get_user_model()


def _receipt():
    return SimpleUploadedFile('proof.png', b'fakepng', content_type='image/png')


def _large_png_receipt():
    import os

    width, height = 700, 700
    img = Image.frombytes('RGB', (width, height), os.urandom(width * height * 3))
    buf = BytesIO()
    img.save(buf, format='PNG', compress_level=1)
    raw = buf.getvalue()
    assert len(raw) > 100 * 1024, f'test fixture must exceed 100 KB (got {len(raw)})'
    assert len(raw) < 5 * 1024 * 1024, f'test fixture must stay under 5 MB (got {len(raw)})'
    return SimpleUploadedFile('large.png', raw, content_type='image/png')


def _small_jpeg_receipt():
    buf = BytesIO()
    Image.new('RGB', (120, 120), color=(250, 250, 250)).save(buf, format='JPEG', quality=85)
    raw = buf.getvalue()
    assert len(raw) < 50 * 1024, 'test fixture must stay under 50 KB'
    return SimpleUploadedFile('small.jpg', raw, content_type='image/jpeg'), len(raw)


def _make_qr(name='QR Main', *, daily_limit=Decimal('100000')):
    return PayInQrAccount.objects.create(
        display_name=name,
        account_display_name='Test Account',
        upi_vpa='test@upi',
        status='active',
        daily_limit_24h=daily_limit,
        sort_order=0,
    )


def _make_package(code='qr_pkg'):
    return PayInPackage.objects.create(
        code=code,
        display_name=code,
        provider='mock',
        gateway_fee_pct=Decimal('1.0000'),
        admin_pct=Decimal('0.2400'),
        super_distributor_pct=Decimal('0.0100'),
        master_distributor_pct=Decimal('0.0200'),
        distributor_pct=Decimal('0.0300'),
        retailer_commission_pct=Decimal('0.0000'),
        min_amount=Decimal('1'),
        max_amount_per_txn=Decimal('200000'),
        sort_order=0,
    )


class QrPayInTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555599',
            email='qr@test.com',
            password='testpass123',
            role='Retailer',
            user_id='QR01',
            first_name='Q',
            last_name='User',
        )
        self.admin = User.objects.create_user(
            phone='9555555598',
            email='admin-qr@test.com',
            password='testpass123',
            role='Admin',
            user_id='ADMQR',
            first_name='A',
            last_name='Admin',
        )
        self.contact = Contact.objects.create(
            user=self.user,
            name='Cust',
            email='c@test.com',
            phone='9876501234',
        )
        self.package = _make_package()
        self.qr = _make_qr()
        sync_package_qr_links(self.package, [self.qr.id], default_qr_account_id=self.qr.id)
        UserPackageAssignment.objects.create(user=self.user, package=self.package)

    def test_checkout_options_include_qr_rail(self):
        options = list_payin_checkout_options_for_user(self.user)
        qr_opts = [o for o in options if o.get('rail_type') == 'qr']
        self.assertEqual(len(qr_opts), 1)
        self.assertTrue(qr_opts[0]['option_key'].startswith('q:'))
        self.assertEqual(qr_opts[0]['qr_account_id'], self.qr.id)

    def test_submit_creates_pending_review(self):
        lm = submit_qr_payin(
            user=self.user,
            package_id=self.package.id,
            qr_account_id=self.qr.id,
            contact_id=self.contact.id,
            amount=Decimal('1000'),
            utr='UTR123456',
            payment_date='2026-08-28',
            receipt_file=_receipt(),
        )
        self.assertEqual(lm.status, 'PENDING_REVIEW')
        self.assertEqual(lm.collection_rail, 'qr')
        self.assertEqual(lm.utr, 'UTR123456')
        self.assertEqual(lm.submitted_amount, Decimal('1000.0000'))

    def test_duplicate_utr_blocked(self):
        submit_qr_payin(
            user=self.user,
            package_id=self.package.id,
            qr_account_id=self.qr.id,
            contact_id=self.contact.id,
            amount=Decimal('500'),
            utr='DUPUTR99',
            payment_date='2026-08-28',
            receipt_file=_receipt(),
        )
        self.assertTrue(utr_exists('DUPUTR99'))
        with self.assertRaises(ValidationError):
            submit_qr_payin(
                user=self.user,
                package_id=self.package.id,
                qr_account_id=self.qr.id,
                contact_id=self.contact.id,
                amount=Decimal('600'),
                utr='duputr99',
                payment_date='2026-08-28',
                receipt_file=_receipt(),
            )

    def test_approve_credits_wallet(self):
        lm = submit_qr_payin(
            user=self.user,
            package_id=self.package.id,
            qr_account_id=self.qr.id,
            contact_id=self.contact.id,
            amount=Decimal('1000'),
            utr='APPUTR001',
            payment_date='2026-08-28',
            receipt_file=_receipt(),
        )
        approved = approve_qr_payin(
            load_money=lm,
            actor=self.admin,
            approved_amount=Decimal('1000'),
        )
        approved.refresh_from_db()
        self.assertEqual(approved.status, 'SUCCESS')
        self.assertGreater(approved.net_credit, Decimal('0'))

    def test_approve_idempotent(self):
        lm = submit_qr_payin(
            user=self.user,
            package_id=self.package.id,
            qr_account_id=self.qr.id,
            contact_id=self.contact.id,
            amount=Decimal('800'),
            utr='IDEMUTR1',
            payment_date='2026-08-28',
            receipt_file=_receipt(),
        )
        approve_qr_payin(load_money=lm, actor=self.admin, approved_amount=Decimal('800'))
        lm.refresh_from_db()
        again = approve_qr_payin(load_money=lm, actor=self.admin, approved_amount=Decimal('800'))
        self.assertEqual(again.status, 'SUCCESS')

    def test_reject_no_wallet_movement(self):
        lm = submit_qr_payin(
            user=self.user,
            package_id=self.package.id,
            qr_account_id=self.qr.id,
            contact_id=self.contact.id,
            amount=Decimal('700'),
            utr='REJUTR01',
            payment_date='2026-08-28',
            receipt_file=_receipt(),
        )
        rejected = reject_qr_payin(
            load_money=lm,
            actor=self.admin,
            reason_code='amount_mismatch',
            reason_text='Wrong amount',
        )
        rejected.refresh_from_db()
        self.assertEqual(rejected.status, 'FAILED')
        self.assertTrue(utr_exists('REJUTR01'))

    def test_pending_counts_toward_daily_limit(self):
        submit_qr_payin(
            user=self.user,
            package_id=self.package.id,
            qr_account_id=self.qr.id,
            contact_id=self.contact.id,
            amount=Decimal('100000'),
            utr='LIMITUTR1',
            payment_date='2026-08-28',
            receipt_file=_receipt(),
        )
        options = list_payin_checkout_options_for_user(self.user)
        main_opt = next(o for o in options if o.get('qr_account_id') == self.qr.id)
        self.assertTrue(main_opt.get('disabled'))
        self.assertIn('limit', (main_opt.get('disabled_reason') or '').lower())

    def test_submit_blocked_when_daily_limit_exhausted(self):
        self.qr.daily_limit_24h = Decimal('1000')
        self.qr.save(update_fields=['daily_limit_24h'])
        submit_qr_payin(
            user=self.user,
            package_id=self.package.id,
            qr_account_id=self.qr.id,
            contact_id=self.contact.id,
            amount=Decimal('1000'),
            utr='LIMITFULL1',
            payment_date='2026-08-28',
            receipt_file=_receipt(),
        )
        with self.assertRaises(ValidationError):
            submit_qr_payin(
                user=self.user,
                package_id=self.package.id,
                qr_account_id=self.qr.id,
                contact_id=self.contact.id,
                amount=Decimal('100'),
                utr='LIMITFULL2',
                payment_date='2026-08-28',
                receipt_file=_receipt(),
            )

    def test_release_utr_allows_reuse(self):
        lm = submit_qr_payin(
            user=self.user,
            package_id=self.package.id,
            qr_account_id=self.qr.id,
            contact_id=self.contact.id,
            amount=Decimal('500'),
            utr='RELUTR01',
            payment_date='2026-08-28',
            receipt_file=_receipt(),
        )
        reject_qr_payin(
            load_money=lm,
            actor=self.admin,
            reason_code='other',
            reason_text='Wrong rejection',
        )
        self.assertTrue(utr_exists('RELUTR01'))
        released = release_qr_utr(
            load_money=lm,
            actor=self.admin,
            internal_note='Ops correction — UTR was valid',
        )
        released.refresh_from_db()
        self.assertEqual(released.utr, '')
        self.assertFalse(utr_exists('RELUTR01'))
        lm2 = submit_qr_payin(
            user=self.user,
            package_id=self.package.id,
            qr_account_id=self.qr.id,
            contact_id=self.contact.id,
            amount=Decimal('500'),
            utr='RELUTR01',
            payment_date='2026-08-28',
            receipt_file=_receipt(),
        )
        self.assertEqual(lm2.utr, 'RELUTR01')
        audit = lm.qr_approval_audits.filter(action='utr_released').first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.reject_reason, 'RELUTR01')

    def test_large_receipt_compressed_on_submit(self):
        lm = submit_qr_payin(
            user=self.user,
            package_id=self.package.id,
            qr_account_id=self.qr.id,
            contact_id=self.contact.id,
            amount=Decimal('1000'),
            utr='BIGRCPT01',
            payment_date='2026-08-28',
            receipt_file=_large_png_receipt(),
        )
        lm.refresh_from_db()
        self.assertLessEqual(lm.receipt_image.size, 100 * 1024)

    def test_small_receipt_left_unchanged(self):
        receipt_file, original_len = _small_jpeg_receipt()
        lm = submit_qr_payin(
            user=self.user,
            package_id=self.package.id,
            qr_account_id=self.qr.id,
            contact_id=self.contact.id,
            amount=Decimal('1000'),
            utr='SMRCPT001',
            payment_date='2026-08-28',
            receipt_file=receipt_file,
        )
        lm.refresh_from_db()
        self.assertEqual(lm.receipt_image.size, original_len)

    def test_qr_operation_detail_includes_json_safe_approval_preview(self):
        from django.urls import reverse
        from rest_framework.test import APIClient

        lm = submit_qr_payin(
            user=self.user,
            package_id=self.package.id,
            qr_account_id=self.qr.id,
            contact_id=self.contact.id,
            amount=Decimal('1000'),
            utr='DETAILUTR1',
            payment_date='2026-08-28',
            receipt_file=_receipt(),
        )
        client = APIClient()
        client.force_authenticate(user=self.admin)
        url = reverse('admin_panel:qr-operations-detail', kwargs={'pk': lm.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('success'))
        data = payload.get('data') or {}
        preview = data.get('approval_preview')
        self.assertIsInstance(preview, dict)
        self.assertIn('snapshot', preview)
        self.assertIn('assignments', preview)
        for role, brief in (preview.get('assignments') or {}).items():
            if brief is not None:
                self.assertIsInstance(brief, dict)
                self.assertIn('id', brief)
                self.assertNotIn('password', brief)
