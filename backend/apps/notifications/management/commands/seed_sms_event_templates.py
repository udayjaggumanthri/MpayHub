from django.core.management.base import BaseCommand

from apps.notifications.catalog import SMS_EVENT_CATALOG
from apps.notifications.models import SmsNotificationTemplate


class Command(BaseCommand):
    help = 'Seed SMS notification template rows from catalog (idempotent).'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for entry in SMS_EVENT_CATALOG:
            obj, was_created = SmsNotificationTemplate.objects.update_or_create(
                event_key=entry['event_key'],
                defaults={
                    'module': entry['module'],
                    'label': entry['label'],
                    'description': entry.get('description', ''),
                    'variable_schema': entry.get('variable_schema', []),
                    'sample_variables': entry.get('sample_variables', {}),
                    'is_enabled': False,
                },
            )
            if was_created:
                created += 1
            else:
                obj.module = entry['module']
                obj.label = entry['label']
                obj.description = entry.get('description', '')
                obj.variable_schema = entry.get('variable_schema', [])
                if not obj.sample_variables:
                    obj.sample_variables = entry.get('sample_variables', {})
                obj.save(
                    update_fields=[
                        'module',
                        'label',
                        'description',
                        'variable_schema',
                        'sample_variables',
                        'updated_at',
                    ]
                )
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'Seeded SMS templates: {created} created, {updated} updated'))
