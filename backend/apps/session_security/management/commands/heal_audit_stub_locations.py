"""
Persist real GeoIP over stub/memory "Test City" audit locations.

Usage:
  python manage.py heal_audit_stub_locations
  python manage.py heal_audit_stub_locations --dry-run
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.session_security.models import UserLoginAuditLog
from apps.session_security.services.audit_query import is_stub_location
from apps.session_security.services.geo import soft_lookup_location


class Command(BaseCommand):
    help = 'Replace memory/Test City audit locations with live GeoIP for the stored IP.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show how many rows would change without writing.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Max rows to process (0 = all).',
        )

    def handle(self, *args, **options):
        dry = bool(options['dry_run'])
        limit = int(options['limit'] or 0)
        qs = UserLoginAuditLog.objects.exclude(ip_address__isnull=True).order_by('id')
        updated = 0
        scanned = 0
        for row in qs.iterator(chunk_size=200):
            if not row.ip_address:
                continue
            loc = row.location if isinstance(row.location, dict) else {}
            if not is_stub_location(loc):
                continue
            scanned += 1
            if limit and scanned > limit:
                break
            healed = soft_lookup_location(row.ip_address)
            if is_stub_location(healed) or not (healed.get('city') or healed.get('country')):
                self.stdout.write(
                    self.style.WARNING(
                        f'skip id={row.id} ip={row.ip_address} (lookup incomplete)'
                    )
                )
                continue
            if dry:
                self.stdout.write(
                    f'would update id={row.id} {loc.get("city")} → {healed.get("city")}'
                )
            else:
                row.location = healed
                row.save(update_fields=['location', 'updated_at'])
            updated += 1
        self.stdout.write(
            self.style.SUCCESS(
                f'{"dry-run " if dry else ""}healed={updated} stub_candidates_scanned={scanned}'
            )
        )
