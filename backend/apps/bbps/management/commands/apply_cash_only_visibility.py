"""Apply cash-only visibility holds to biller master rows."""
from django.core.management.base import BaseCommand

from apps.bbps.service_flow.catalog_visibility import apply_cash_only_visibility_for_env
from apps.bbps.service_flow.catalog_ux_settings import is_cash_only_for_users
from apps.integrations.billavenue.registry import normalize_billavenue_mode


class Command(BaseCommand):
    help = 'Apply cash-only visibility rules to biller master rows for uat/prod.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--environment',
            choices=['uat', 'prod', 'both'],
            default='both',
            help='BillAvenue environment to process (default: both)',
        )

    def handle(self, *args, **options):
        env_opt = str(options.get('environment') or 'both').strip().lower()
        envs = ['uat', 'prod'] if env_opt == 'both' else [normalize_billavenue_mode(env_opt)]
        for env in envs:
            if not is_cash_only_for_users(env):
                self.stdout.write(self.style.WARNING(f'{env.upper()}: cash-only is OFF — skipping apply'))
                continue
            stats = apply_cash_only_visibility_for_env(env)
            self.stdout.write(
                self.style.SUCCESS(
                    f'{env.upper()}: hidden={stats["hidden"]} restored={stats["restored"]} '
                    f'skipped_admin={stats["skipped_admin"]}'
                )
            )
