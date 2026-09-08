"""
Verify ImageField DB names exist in default_storage (local or S3).

  python manage.py verify_media_storage
  python manage.py verify_media_storage --limit 20
"""

from __future__ import annotations

from django.apps import apps
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import models


class Command(BaseCommand):
    help = 'Check that ImageField/FileField values exist on default_storage.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Max non-empty fields to check per model field (default 50).',
        )

    def handle(self, *args, **options):
        limit = max(1, options['limit'])
        checked = 0
        missing = 0
        errors = 0

        for model in apps.get_models():
            file_fields = [
                f
                for f in model._meta.get_fields()
                if isinstance(f, (models.FileField, models.ImageField))
            ]
            if not file_fields:
                continue

            for field in file_fields:
                qs = (
                    model.objects.exclude(**{f'{field.name}': ''})
                    .exclude(**{f'{field.name}': None})
                    .order_by('-pk')[:limit]
                )
                for obj in qs:
                    file_value = getattr(obj, field.name)
                    name = file_value.name if file_value else ''
                    if not name:
                        continue
                    checked += 1
                    try:
                        ok = default_storage.exists(name)
                    except Exception as exc:  # noqa: BLE001 — report and continue
                        errors += 1
                        self.stderr.write(
                            f'ERROR {model._meta.label}.{field.name} pk={obj.pk} name={name!r}: {exc}'
                        )
                        continue
                    if ok:
                        self.stdout.write(
                            f'OK    {model._meta.label}.{field.name} pk={obj.pk} {name}'
                        )
                    else:
                        missing += 1
                        self.stderr.write(
                            f'MISS  {model._meta.label}.{field.name} pk={obj.pk} {name}'
                        )

        self.stdout.write(
            self.style.NOTICE(f'Checked={checked} missing={missing} errors={errors}')
        )
        if missing or errors:
            raise SystemExit(1)
