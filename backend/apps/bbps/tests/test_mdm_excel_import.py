from io import BytesIO
from unittest.mock import patch

from django.test import TestCase
from openpyxl import Workbook
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.bbps.catalog.mdm_import.excel_parser import parse_mdm_excel
from apps.bbps.catalog.mdm_import.queue_service import create_job_from_upload, drain_job
from apps.bbps.catalog.mdm_import.seed import seed_masters_from_excel_rows
from apps.bbps.models import BbpsBillerMaster, BbpsMdmImportItem, BbpsMdmImportJob, BbpsSyncUsageLog
from apps.bbps.service_flow.mdm_sync_batch import MDM_BATCH_MAX_IDS
from apps.integrations.billavenue.registry import activate_billavenue_config, get_or_create_billavenue_mode_row
from django.utils import timezone


def _xlsx_bytes(headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _admin():
    user = User.objects.create_user(
        phone='9199988801',
        email='bbps_mdm_import@example.com',
        password='pass12345',
        role='Admin',
        user_id='BBPSMDM1',
        first_name='MDM',
        last_name='Import',
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


class ExcelParserTests(TestCase):
    def test_parse_mdm_416_style_headers_dedupe_and_skip_invalid(self):
        raw = _xlsx_bytes(
            ['blr_id', 'blr_name', 'blr_category_name', 'blr_coverage'],
            [
                ['ATPOST000NAT01', 'Airtel Postpaid', 'Mobile Postpaid', 'India'],
                ['ATPOST000NAT01', 'Dup', 'Mobile Postpaid', 'India'],
                ['BAD ID!', 'Bad', 'X', 'Y'],
                ['HDFC00000NAT01', 'HDFC', 'Credit Card', 'India'],
            ],
        )
        rows = parse_mdm_excel(raw, filename='mdm.xlsx')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['biller_id'], 'ATPOST000NAT01')
        self.assertEqual(rows[0]['biller_name'], 'Airtel Postpaid')
        self.assertEqual(rows[0]['biller_category'], 'Mobile Postpaid')
        self.assertEqual(rows[1]['biller_id'], 'HDFC00000NAT01')

    def test_alias_headers_and_empty_raises(self):
        raw = _xlsx_bytes(['biller_id', 'biller_name'], [['', 'Nope']])
        with self.assertRaises(ValueError):
            parse_mdm_excel(raw, filename='empty.xlsx')


class SeedAndQueueTests(TestCase):
    def setUp(self):
        uat = get_or_create_billavenue_mode_row('uat')
        uat.enabled = True
        uat.mdm_max_calls_per_day = 15
        uat.save()
        activate_billavenue_config(uat)

    def test_excel_seed_updates_existing_master(self):
        BbpsBillerMaster.objects.create(
            environment='uat',
            biller_id='SEED0001',
            biller_name='Old',
            biller_category='OldCat',
            biller_coverage='OldCov',
            source_type='manual',
            is_active_local=True,
        )
        stats = seed_masters_from_excel_rows(
            environment='uat',
            rows=[
                {
                    'biller_id': 'SEED0001',
                    'biller_name': 'New Name',
                    'biller_category': 'Credit Card',
                    'biller_coverage': 'India',
                }
            ],
        )
        self.assertEqual(stats['updated'], 1)
        row = BbpsBillerMaster.objects.get(environment='uat', biller_id='SEED0001')
        self.assertEqual(row.biller_name, 'New Name')
        self.assertEqual(row.biller_category, 'Credit Card')
        self.assertEqual(row.source_type, 'excel_import')

    @patch('apps.bbps.catalog.mdm_import.queue_service.run_mdm_sync_batch')
    def test_drain_respects_quota_and_batches(self, mock_batch):
        def _batch(ids, **kwargs):
            # Mimic real quota increment so drain stops when exhausted.
            today = timezone.localdate()
            row, _ = BbpsSyncUsageLog.objects.get_or_create(
                usage_date=today,
                environment='uat',
                defaults={'call_count': 0, 'last_status': 'ok'},
            )
            row.call_count = int(row.call_count or 0) + 1
            row.last_status = 'ok'
            row.save(update_fields=['call_count', 'last_status', 'updated_at'])
            return {'updated_count': len(ids), 'biller_count': len(ids)}

        mock_batch.side_effect = _batch

        ids = [f'BILL{i:05d}' for i in range(4500)]
        raw = _xlsx_bytes(
            ['blr_id', 'blr_name', 'blr_category_name', 'blr_coverage'],
            [[bid, bid, 'Cat', 'India'] for bid in ids],
        )

        # Force only 1 remaining call today (max 15 → used 14)
        BbpsSyncUsageLog.objects.create(
            usage_date=timezone.localdate(),
            environment='uat',
            call_count=14,
            last_status='ok',
        )

        result = create_job_from_upload(
            file_obj=BytesIO(raw),
            filename='big.xlsx',
            environment='uat',
            auto_drain=True,
        )
        job = result['job']
        self.assertEqual(job.total_ids, 4500)
        self.assertEqual(mock_batch.call_count, 1)
        self.assertEqual(len(mock_batch.call_args[0][0]), MDM_BATCH_MAX_IDS)
        job.refresh_from_db()
        self.assertEqual(job.synced_ids, 2000)
        self.assertEqual(job.pending_ids, 2500)
        self.assertEqual(job.status, 'partial')

        # Reset to 2 remaining calls; drain should run 2 batches and finish
        usage = BbpsSyncUsageLog.objects.get(usage_date=timezone.localdate(), environment='uat')
        usage.call_count = 13
        usage.save(update_fields=['call_count'])
        mock_batch.reset_mock()
        drain = drain_job(job.pk)
        self.assertEqual(mock_batch.call_count, 2)
        self.assertEqual(drain['synced_ids'], 4500)
        self.assertEqual(drain['pending_ids'], 0)
        self.assertEqual(drain['status'], 'completed')


class MdmImportApiTests(TestCase):
    def setUp(self):
        uat = get_or_create_billavenue_mode_row('uat')
        uat.enabled = True
        uat.save()
        activate_billavenue_config(uat)
        self.client, self.user = _admin()

    @patch('apps.bbps.catalog.mdm_import.queue_service.run_mdm_sync_batch')
    def test_upload_endpoint(self, mock_batch):
        mock_batch.return_value = {'updated_count': 1, 'biller_count': 1}
        from django.core.files.uploadedfile import SimpleUploadedFile

        raw = _xlsx_bytes(
            ['blr_id', 'blr_name', 'blr_category_name', 'blr_coverage'],
            [['API0001NAT01', 'API Biller', 'Credit Card', 'India']],
        )
        upload = SimpleUploadedFile(
            'mdm.xlsx',
            raw,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        res = self.client.post(
            '/api/bbps/admin/mdm-import/upload/',
            {'file': upload, 'environment': 'uat'},
            format='multipart',
        )
        self.assertEqual(res.status_code, 201, res.content)
        self.assertTrue(res.data['success'])
        self.assertEqual(res.data['data']['job']['total_ids'], 1)
        self.assertTrue(BbpsMdmImportJob.objects.filter(environment='uat').exists())
        self.assertTrue(BbpsMdmImportItem.objects.filter(biller_id='API0001NAT01').exists())
        self.assertTrue(
            BbpsBillerMaster.objects.filter(environment='uat', biller_id='API0001NAT01').exists()
        )

    @patch('apps.bbps.catalog.mdm_import.queue_service.run_mdm_sync_batch')
    def test_destroy_job_endpoint(self, mock_batch):
        mock_batch.side_effect = Exception('should not drain after destroy')
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.bbps.catalog.mdm_import.queue_service import create_job_from_upload

        raw = _xlsx_bytes(
            ['blr_id', 'blr_name', 'blr_category_name', 'blr_coverage'],
            [
                ['DEST001NAT01', 'Destroy Me', 'Credit Card', 'India'],
                ['DEST002NAT01', 'Destroy Me 2', 'Credit Card', 'India'],
            ],
        )
        upload = SimpleUploadedFile(
            'destroy.xlsx',
            raw,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        created = create_job_from_upload(
            file_obj=upload,
            filename='destroy.xlsx',
            environment='uat',
            user=self.user,
            auto_drain=False,
        )
        job = created['job']
        self.assertEqual(job.pending_ids, 2)

        res = self.client.post(
            f'/api/bbps/admin/mdm-import/jobs/{job.pk}/destroy/',
            {'reason': 'Test destroy'},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data['success'])
        job.refresh_from_db()
        self.assertTrue(job.is_deleted)
        self.assertEqual(job.status, 'cancelled')
        self.assertEqual(job.pending_ids, 0)
        self.assertFalse(
            BbpsMdmImportJob.objects.filter(pk=job.pk, is_deleted=False).exists()
        )
        # Process must not revive it
        again = self.client.post(f'/api/bbps/admin/mdm-import/jobs/{job.pk}/process/')
        self.assertEqual(again.status_code, 404)
