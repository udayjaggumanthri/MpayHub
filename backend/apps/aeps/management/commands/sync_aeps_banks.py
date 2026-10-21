from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.aeps.models import AepsProviderConfig
from apps.aeps.services.products import sync_bank_iin_cache


class Command(BaseCommand):
    help = 'Sync Fingpay bank IIN lists into AEPS cache (schedule daily via cron)'

    def handle(self, *args, **options):
        n = sync_bank_iin_cache()
        now = timezone.now()
        AepsProviderConfig.objects.filter(is_active=True, is_deleted=False).update(banks_last_synced_at=now)
        self.stdout.write(self.style.SUCCESS(f'Synced {n} bank IIN rows at {now.isoformat()}'))