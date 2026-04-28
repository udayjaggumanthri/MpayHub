import csv

from django.core.management.base import BaseCommand

from apps.bbps.models import BbpsBillerMaster


class Command(BaseCommand):
    help = 'Load/update BBPS UAT biller master from CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str)

    def handle(self, *args, **options):
        path = options['csv_path']
        created = 0
        updated = 0
        with open(path, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                biller_id = (row.get('biller_id') or row.get('billerId') or '').strip()
                if not biller_id:
                    continue
                _, was_created = BbpsBillerMaster.objects.update_or_create(
                    biller_id=biller_id,
                    defaults={
                        'biller_name': (row.get('biller_name') or row.get('billerName') or '').strip(),
                        'biller_category': (row.get('biller_category') or row.get('billerCategory') or '').strip(),
                        'biller_status': (row.get('biller_status') or row.get('billerStatus') or 'ACTIVE').strip(),
                        'raw_payload': row,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
        self.stdout.write(self.style.SUCCESS(f'Loaded UAT CSV: created={created}, updated={updated}'))
