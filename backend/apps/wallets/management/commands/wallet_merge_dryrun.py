"""
Dry-run wallet consolidation: snapshot every user, write CSV, move no money.
"""
from django.core.management.base import BaseCommand

from apps.wallets.consolidation import dry_run


class Command(BaseCommand):
    help = (
        'Snapshot all wallet balances into WalletMergeAudit (status=dry_run) '
        'and optionally write a CSV. Does not move any money.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            dest='csv_path',
            default='wallet_merge_dryrun.csv',
            help='Output CSV path (default: wallet_merge_dryrun.csv)',
        )
        parser.add_argument(
            '--no-csv',
            action='store_true',
            help='Skip writing a CSV file',
        )

    def handle(self, *args, **options):
        csv_path = None if options.get('no_csv') else options.get('csv_path')
        summary = dry_run(write_csv_path=csv_path)
        self.stdout.write(self.style.SUCCESS(
            f"Dry-run complete: {summary['users']} user(s)\n"
            f"  grand_main={summary['grand_main']}\n"
            f"  grand_bbps={summary['grand_bbps']}\n"
            f"  grand_commission={summary['grand_commission']}\n"
            f"  grand_profit={summary['grand_profit']}\n"
            f"  grand_merged={summary['grand_merged']}\n"
            f"  grand_after={summary['grand_after']}"
        ))
        if csv_path:
            self.stdout.write(f"CSV written to {csv_path}")
