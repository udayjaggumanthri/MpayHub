"""Seed AppModule and RoleModulePermission rows from the default catalog."""
from django.core.management.base import BaseCommand

from apps.core.module_permissions import seed_modules_and_permissions


class Command(BaseCommand):
    help = 'Seed portal AppModule / RoleModulePermission matrix (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset enabled flags to the default catalog for existing rows.',
        )

    def handle(self, *args, **options):
        result = seed_modules_and_permissions(reset=bool(options['reset']))
        self.stdout.write(self.style.SUCCESS(f'Seeded module permissions: {result}'))
