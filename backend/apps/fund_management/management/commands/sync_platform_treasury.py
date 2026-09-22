"""
Sync Admin / Super Admin login wallets onto the shared platform treasury.

Usage:
  python manage.py sync_platform_treasury
"""
from django.core.management.base import BaseCommand

from apps.fund_management.platform_settlement import sync_platform_operator_treasury


class Command(BaseCommand):
    help = 'Merge operator login Main balances + commission ledgers onto PLATFORM_PAYIN_SETTLEMENT_USER_ID treasury'

    def handle(self, *args, **options):
        stats = sync_platform_operator_treasury()
        if not stats.get('ok'):
            self.stderr.write(self.style.ERROR(str(stats)))
            return
        self.stdout.write(self.style.SUCCESS(
            f"Treasury {stats['treasury_id']}: merged {stats['ledger_groups_merged']} ledger groups, "
            f"removed {stats['ledger_rows_removed']} duplicate rows, "
            f"moved ₹{stats['wallet_moved']} onto Main."
        ))
