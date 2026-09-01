from django.core.management.base import BaseCommand

from apps.bbps.services import warmup_bbps_catalog_cache


class Command(BaseCommand):
    help = 'Warm BBPS category and biller list caches (read-path only).'

    def handle(self, *args, **options):
        try:
            stats = warmup_bbps_catalog_cache()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Warmed BBPS catalog: {stats["categories"]} categories, '
                    f'{stats["biller_lists"]} biller lists.'
                )
            )
        except Exception as exc:
            self.stderr.write(self.style.WARNING(f'BBPS catalog warmup skipped: {exc}'))
