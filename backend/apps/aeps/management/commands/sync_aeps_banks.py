from django.core.management.base import BaseCommand

from apps.aeps.services.products import sync_bank_iin_cache


class Command(BaseCommand):
    help = 'Sync Fingpay bank IIN lists into AEPS cache'

    def handle(self, *args, **options):
        n = sync_bank_iin_cache()
        self.stdout.write(self.style.SUCCESS(f'Synced {n} bank IIN rows'))
