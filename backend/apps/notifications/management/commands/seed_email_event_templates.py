from django.core.management.base import BaseCommand

from apps.notifications.email_catalog import EMAIL_EVENT_CATALOG
from apps.notifications.models import EmailNotificationTemplate


class Command(BaseCommand):
    help = 'Seed email notification template rows from catalog (idempotent).'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for entry in EMAIL_EVENT_CATALOG:
            defaults = {
                'module': entry['module'],
                'label': entry['label'],
                'description': entry.get('description', ''),
                'variable_schema': entry.get('variable_schema', []),
                'sample_variables': entry.get('sample_variables', {}),
                'is_enabled': False,
                'subject_template': entry.get('default_subject', ''),
                'body_html_template': entry.get('default_body_html', ''),
                'body_plain_template': entry.get('default_body_plain', ''),
            }
            obj, was_created = EmailNotificationTemplate.objects.update_or_create(
                event_key=entry['event_key'],
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                obj.module = entry['module']
                obj.label = entry['label']
                obj.description = entry.get('description', '')
                obj.variable_schema = entry.get('variable_schema', [])
                if not obj.subject_template:
                    obj.subject_template = entry.get('default_subject', '')
                if not obj.body_html_template:
                    obj.body_html_template = entry.get('default_body_html', '')
                if not obj.body_plain_template:
                    obj.body_plain_template = entry.get('default_body_plain', '')
                if not obj.sample_variables:
                    obj.sample_variables = entry.get('sample_variables', {})
                obj.save(
                    update_fields=[
                        'module',
                        'label',
                        'description',
                        'variable_schema',
                        'subject_template',
                        'body_html_template',
                        'body_plain_template',
                        'sample_variables',
                        'updated_at',
                    ]
                )
                updated += 1
        self.stdout.write(
            self.style.SUCCESS(f'Seeded email templates: {created} created, {updated} updated')
        )
