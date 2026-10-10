"""Ask BillAvenue for a final status on due in-flight BBPS payments."""
from django.core.management.base import BaseCommand

from apps.bbps.service_flow.status_service import sync_due_pending_statuses


class Command(BaseCommand):
    help = 'Sync due Pay initiated / Awaited / Pending BBPS payments via transaction-status.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50)
        parser.add_argument('--minutes', type=int, default=15)

    def handle(self, *args, **options):
        limit = int(options.get('limit') or 50)
        minutes = int(options.get('minutes') or 15)
        n = sync_due_pending_statuses(limit=limit, minimum_minutes=minutes)
        self.stdout.write(self.style.SUCCESS(f'Checked {n} due BBPS payment(s)'))
