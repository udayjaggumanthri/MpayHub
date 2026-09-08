"""
Upload local MEDIA_ROOT files to S3 when USE_S3=True.

Skips objects that already exist with the same size. Does not delete remote files.
Safe to run on every backend start (idempotent).

  python manage.py sync_local_media_to_s3
  python manage.py sync_local_media_to_s3 --dry-run
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Sync local media/ files to S3 (skip existing same-size objects).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List uploads without writing to S3.',
        )

    def handle(self, *args, **options):
        dry_run = bool(options['dry_run'])

        if not getattr(settings, 'USE_S3', False):
            self.stdout.write(self.style.WARNING('USE_S3=False — skip local→S3 sync.'))
            return

        bucket = (getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None) or '').strip()
        prefix = (getattr(settings, 'AWS_S3_MEDIA_PREFIX', None) or '').strip().strip('/')
        region = (getattr(settings, 'AWS_S3_REGION_NAME', None) or 'ap-south-1').strip()
        if not bucket or not prefix:
            raise CommandError('USE_S3=True requires AWS_STORAGE_BUCKET_NAME and AWS_S3_MEDIA_PREFIX')

        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.is_dir():
            self.stdout.write(
                self.style.WARNING(f'No local media dir at {media_root} — nothing to sync.')
            )
            return

        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError as exc:
            raise CommandError('boto3 is required for media sync') from exc

        client = boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        )

        uploaded = 0
        skipped = 0
        errors = 0

        for path in sorted(media_root.rglob('*')):
            if not path.is_file():
                continue
            if path.name.startswith('.') or path.name == 'Thumbs.db':
                continue

            relative = path.relative_to(media_root).as_posix()
            key = f'{prefix}/{relative}'
            local_size = path.stat().st_size

            needs_upload = True
            try:
                head = client.head_object(Bucket=bucket, Key=key)
                remote_size = int(head.get('ContentLength') or 0)
                if remote_size == local_size:
                    skipped += 1
                    needs_upload = False
            except ClientError as exc:
                code = str((exc.response or {}).get('Error', {}).get('Code', ''))
                # Missing object → upload. Other errors → report.
                if code not in ('404', 'NoSuchKey', 'NotFound'):
                    errors += 1
                    self.stderr.write(f'HEAD error {key}: {exc}')
                    continue
            except Exception as exc:  # noqa: BLE001
                errors += 1
                self.stderr.write(f'HEAD error {key}: {exc}')
                continue

            if not needs_upload:
                continue

            content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
            self.stdout.write(
                f'{"DRY " if dry_run else ""}UPLOAD {relative} -> s3://{bucket}/{key} ({local_size} bytes)'
            )
            if dry_run:
                uploaded += 1
                continue
            try:
                client.upload_file(
                    str(path),
                    bucket,
                    key,
                    ExtraArgs={'ContentType': content_type},
                )
                uploaded += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                self.stderr.write(f'UPLOAD failed {key}: {exc}')

        msg = (
            f'Sync done: uploaded={uploaded} skipped_existing={skipped} '
            f'errors={errors} dry_run={dry_run}'
        )
        self.stdout.write(self.style.SUCCESS(msg) if errors == 0 else self.style.WARNING(msg))
        if errors:
            raise SystemExit(1)
