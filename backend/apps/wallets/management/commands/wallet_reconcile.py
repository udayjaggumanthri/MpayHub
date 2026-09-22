"""
Post-merge reconciliation: assert non-main wallets are zero and totals match.
Exit code 1 on any mismatch.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.wallets.consolidation import reconcile


class Command(BaseCommand):
    help = (
        'Assert wallet consolidation invariants: non-main wallets at zero, '
        'SUM(all) == SUM(main). Exit non-zero on mismatch.'
    )

    def handle(self, *args, **options):
        result = reconcile()
        self.stdout.write(
            f"total_all={result['total_all']} total_main={result['total_main']} "
            f"legacy_nonzero={result['legacy_nonzero']} "
            f"archived_residual={result['archived_residual']} "
            f"merged_audits={result['merged_audit_count']}"
        )
        if not result['ok']:
            for err in result['errors']:
                self.stderr.write(self.style.ERROR(err))
            raise CommandError('Wallet reconcile FAILED')
        self.stdout.write(self.style.SUCCESS('Wallet reconcile OK'))
