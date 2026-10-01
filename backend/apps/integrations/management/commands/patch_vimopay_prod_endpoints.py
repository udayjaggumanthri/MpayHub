"""
Idempotent merge of Vidual production endpoint URLs into vimopay ApiMaster.config_json.

Does not change secrets, base_url, webhook, or status. Safe on live:
  python manage.py patch_vimopay_prod_endpoints
  python manage.py patch_vimopay_prod_endpoints --dry-run
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.integrations.models import ApiMaster

PROD_ENDPOINTS = {
    'authorize': 'https://prod.vidual.in/payoutapi/api/Signature/Authorize',
    'payout': 'https://prod.vidual.in/payoutapi/api/Payment/payout',
    'purpose_list': 'https://prod.vidual.in/masterapi/api/master/purposelist',
    'bank_list': 'https://prod.vidual.in/masterapi/api/master/banklist',
    'state_list': 'https://prod.vidual.in/masterapi/api/master/statelist',
}


class Command(BaseCommand):
    help = 'Merge Vidual production full endpoint URLs into vimopay payout ApiMaster config_json.endpoints'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without saving',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite existing endpoints keys even if already set',
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get('dry_run'))
        force = bool(options.get('force'))
        qs = ApiMaster.objects.filter(provider_type='payout', provider_code='vimopay').order_by(
            '-is_default', '-id'
        )
        if not qs.exists():
            self.stdout.write(self.style.WARNING('No vimopay payout ApiMaster rows found.'))
            return

        updated = 0
        for master in qs:
            cfg = dict(master.config_json) if isinstance(master.config_json, dict) else {}
            endpoints = dict(cfg.get('endpoints') or {}) if isinstance(cfg.get('endpoints'), dict) else {}
            before = dict(endpoints)
            changed = False
            for key, url in PROD_ENDPOINTS.items():
                if force or not str(endpoints.get(key) or '').strip():
                    if endpoints.get(key) != url:
                        endpoints[key] = url
                        changed = True
                elif str(endpoints.get(key) or '').strip() != url:
                    # Already set to something else — leave unless --force
                    pass

            if not changed:
                self.stdout.write(
                    f'[{master.id}] {master.provider_name}: endpoints already set, no change'
                )
                continue

            self.stdout.write(
                f'[{master.id}] {master.provider_name} '
                f'({"dry-run" if dry_run else "updating"}):\n'
                f'  before={before}\n'
                f'  after={endpoints}'
            )
            if dry_run:
                continue
            cfg['endpoints'] = endpoints
            master.config_json = cfg
            master.save(update_fields=['config_json', 'updated_at'])
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Updated {updated} row(s). dry_run={dry_run} force={force}'
            )
        )
