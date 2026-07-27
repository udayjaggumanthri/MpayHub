"""
Reconcile missing member identity fields without touching legacy user_id or credentials.

Usage:
  python manage.py reconcile_member_identity
  python manage.py reconcile_member_identity --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.authentication.models import MemberNumberSequence, User
from apps.users.identity import SEQUENCE_KEY, format_display_code, format_member_id


class Command(BaseCommand):
    help = 'Idempotently assign member_number/member_id/display_code to users missing them.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be assigned without writing.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry = bool(options.get('dry_run'))
        pending = list(
            User.objects.filter(member_number__isnull=True).order_by('created_at', 'id')
        )
        max_existing = (
            User.objects.exclude(member_number__isnull=True)
            .order_by('-member_number')
            .values_list('member_number', flat=True)
            .first()
        ) or 0
        next_n = int(max_existing) + 1
        assigned = 0
        for user in pending:
            member_id = format_member_id(next_n)
            display_code = format_display_code(user.role, next_n)
            self.stdout.write(
                f'assign pk={user.pk} legacy={user.user_id!r} -> '
                f'{next_n} {member_id} {display_code}'
            )
            if not dry:
                user.member_number = next_n
                user.member_id = member_id
                user.display_code = display_code
                user.save(update_fields=['member_number', 'member_id', 'display_code', 'updated_at'])
            assigned += 1
            next_n += 1

        final_max = (
            User.objects.exclude(member_number__isnull=True)
            .order_by('-member_number')
            .values_list('member_number', flat=True)
            .first()
        ) or 0
        if not dry:
            MemberNumberSequence.objects.update_or_create(
                key=SEQUENCE_KEY,
                defaults={'next_value': int(final_max) + 1},
            )
        self.stdout.write(
            self.style.SUCCESS(
                f'Reconcile complete: {assigned} users '
                f'{"(dry-run)" if dry else "updated"}; next_value={int(final_max) + 1}'
            )
        )
