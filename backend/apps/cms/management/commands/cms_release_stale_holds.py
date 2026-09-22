"""Release stale CMS holds (initiated past hold_ttl_hours)."""
from django.core.management.base import BaseCommand

from apps.cms.services.registry import get_active_cms_config
from apps.cms.services.wallet import release_stale_holds


class Command(BaseCommand):
    help = 'Release CMS wallet holds older than provider hold_ttl_hours (or --hours).'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=None)

    def handle(self, *args, **options):
        hours = options.get('hours')
        if hours is None:
            try:
                hours = get_active_cms_config(require_secrets=False).hold_ttl_hours
            except Exception:
                hours = 24
        n = release_stale_holds(older_than_hours=int(hours or 24))
        self.stdout.write(self.style.SUCCESS(f'Released {n} stale CMS hold(s)'))
