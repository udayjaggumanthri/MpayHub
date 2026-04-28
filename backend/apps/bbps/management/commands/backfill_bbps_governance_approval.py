from django.core.management.base import BaseCommand

from apps.bbps.models import BbpsProviderBillerMap, BbpsServiceProvider


class Command(BaseCommand):
    help = 'Backfill BBPS governance approval metadata for providers and maps.'

    def handle(self, *args, **options):
        provider_count = 0
        map_count = 0

        for row in BbpsServiceProvider.objects.filter(is_deleted=False):
            md = dict(row.metadata or {})
            md.setdefault('approval_status', 'approved' if row.is_active else 'pending')
            md.setdefault('auto_synced', False)
            row.metadata = md
            row.save(update_fields=['metadata', 'updated_at'])
            provider_count += 1

        for row in BbpsProviderBillerMap.objects.filter(is_deleted=False):
            md = dict(row.metadata or {})
            md.setdefault('approval_status', 'approved' if row.is_active else 'pending')
            md.setdefault('auto_synced', False)
            row.metadata = md
            row.save(update_fields=['metadata', 'updated_at'])
            map_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Backfill completed: providers={provider_count}, maps={map_count}'
            )
        )
