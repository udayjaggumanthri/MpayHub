from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.catalog import (
    OBSOLETE_SMS_EVENT_KEYS,
    SMS_EVENT_CATALOG,
)
from apps.notifications.models import SmsNotificationTemplate
from apps.notifications.services.template_sync import MAPPING_SOURCE_DEFAULT


class Command(BaseCommand):
    help = (
        'Seed SMS notification template rows from catalog (idempotent; '
        'never resets enable/template_id). Does not overwrite maps after MSG91 auto-sync. '
        'Use --reset-maps to force-replace all maps from catalog defaults.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-maps',
            action='store_true',
            help='Overwrite variable_map for every event with catalog default_variable_map',
        )

    def handle(self, *args, **options):
        reset_maps = bool(options.get('reset_maps'))
        created = 0
        updated = 0
        maps_fixed = 0
        for entry in SMS_EVENT_CATALOG:
            event_key = entry['event_key']
            defaults = entry.get('default_variable_map') or {}
            existing = SmsNotificationTemplate.objects.filter(event_key=event_key).first()
            if existing is None:
                template_id = ''
                variable_map = dict(defaults) if isinstance(defaults, dict) else {}
                is_enabled = False
                if event_key == 'auth.otp.verification':
                    for legacy_key in ('auth.otp.password_reset', 'auth.otp.mpin_reset'):
                        legacy = SmsNotificationTemplate.objects.filter(
                            event_key=legacy_key, is_deleted=False
                        ).first()
                        if legacy and (legacy.template_id or '').strip():
                            template_id = legacy.template_id.strip()
                            if legacy.variable_map:
                                variable_map = dict(legacy.variable_map)
                            is_enabled = bool(legacy.is_enabled)
                            break
                SmsNotificationTemplate.objects.create(
                    event_key=event_key,
                    module=entry['module'],
                    label=entry['label'],
                    description=entry.get('description', ''),
                    variable_schema=entry.get('variable_schema', []),
                    sample_variables=entry.get('sample_variables', {}),
                    is_enabled=is_enabled,
                    template_id=template_id,
                    variable_map=variable_map if isinstance(variable_map, dict) else {},
                    mapping_source=MAPPING_SOURCE_DEFAULT if variable_map else '',
                )
                created += 1
                continue

            existing.module = entry['module']
            existing.label = entry['label']
            existing.description = entry.get('description', '')
            existing.variable_schema = entry.get('variable_schema', [])
            if not existing.sample_variables:
                existing.sample_variables = entry.get('sample_variables', {})

            current_map = existing.variable_map if isinstance(existing.variable_map, dict) else {}
            already_synced = bool(existing.msg91_synced_at) or (
                (existing.mapping_source or '') == 'auto'
            )

            if reset_maps and defaults:
                existing.variable_map = dict(defaults)
                existing.mapping_source = MAPPING_SOURCE_DEFAULT
                maps_fixed += 1
            elif not current_map and defaults and not already_synced:
                existing.variable_map = dict(defaults)
                existing.mapping_source = MAPPING_SOURCE_DEFAULT
                maps_fixed += 1

            existing.save(
                update_fields=[
                    'module',
                    'label',
                    'description',
                    'variable_schema',
                    'sample_variables',
                    'variable_map',
                    'mapping_source',
                    'updated_at',
                ]
            )
            updated += 1

        retired = 0
        now = timezone.now()
        for obsolete_key in OBSOLETE_SMS_EVENT_KEYS:
            qs = SmsNotificationTemplate.objects.filter(event_key=obsolete_key, is_deleted=False)
            for row in qs:
                row.is_deleted = True
                row.deleted_at = now
                row.is_enabled = False
                row.save(update_fields=['is_deleted', 'deleted_at', 'is_enabled', 'updated_at'])
                retired += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded SMS templates: {created} created, {updated} updated, '
                f'{maps_fixed} maps fixed, {retired} obsolete retired'
            )
        )
