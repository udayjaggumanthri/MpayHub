"""Leave in-flight BBPS wallet reserves in place until status is final."""
from django.core.management.base import BaseCommand

from apps.bbps.service_flow.user_wallet_settlement import release_stale_bbps_holds


class Command(BaseCommand):
    help = (
        'In-flight BBPS holds (Pay initiated, Awaited, Pending) are not released. '
        'Reports how many aged holds were left reserved.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=48)

    def handle(self, *args, **options):
        hours = int(options.get('hours') or 48)
        n = release_stale_bbps_holds(older_than_hours=hours)
        self.stdout.write(self.style.SUCCESS(f'Released {n} stale BBPS hold(s)'))
