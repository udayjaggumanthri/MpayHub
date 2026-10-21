"""Push outbound 3-way recon for a date (default: yesterday)."""
from django.core.management.base import BaseCommand

from apps.aeps.services import recon as recon_svc


class Command(BaseCommand):
    help = 'Push outbound Fingpay 3-way recon for --date (YYYY-MM-DD or DD-MM-YYYY). Default: yesterday.'

    def add_arguments(self, parser):
        parser.add_argument('--date', dest='txn_date', default='', help='Txn date to reconcile')

    def handle(self, *args, **options):
        txn_date = (options.get('txn_date') or '').strip() or None
        result = recon_svc.run_outbound_recon(txn_date=txn_date, actor=None)
        self.stdout.write(self.style.SUCCESS(str(result)))
