"""
Drain pending Excel MDM import jobs using remaining daily BillAvenue quota.

Example crontab (once per day after midnight IST):
  15 0 * * * cd /home/ubuntu/MpayHub/backend && .venv/bin/python manage.py process_bbps_mdm_imports
"""

from django.core.management.base import BaseCommand

from apps.bbps.catalog.mdm_import.processor import process_pending_jobs


class Command(BaseCommand):
    help = 'Process pending BBPS Excel MDM import jobs for UAT/PROD using remaining daily MDM quota.'

    def add_arguments(self, parser):
        parser.add_argument('--environment', choices=['uat', 'prod'], default=None)
        parser.add_argument('--max-jobs', type=int, default=10)

    def handle(self, *args, **options):
        env = options.get('environment')
        max_jobs = int(options.get('max_jobs') or 10)
        out = process_pending_jobs(environment=env, max_jobs=max_jobs)
        self.stdout.write(
            self.style.SUCCESS(
                f'Processed {out.get("processed", 0)} job(s); results={out.get("results")}'
            )
        )
