"""
Link existing bank accounts to contacts for R000016 (user 36) only.

Allowlist:
  bank 10 (32663600155) → contact 91 (Bobby / 9642425240)
  bank 11 (38370894141) → contact 94 (Mohit / 9777131431)

Usage:
  python manage.py link_r000016_bank_contacts --dry-run
  python manage.py link_r000016_bank_contacts
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.bank_accounts.models import BankAccount
from apps.contacts.models import Contact

# (bank_account_id, contact_id, expected_account_number, expected_contact_phone)
LINKS = (
    (10, 91, '32663600155', '9642425240'),
    (11, 94, '38370894141', '9777131431'),
)
OWNER_USER_ID = 36


class Command(BaseCommand):
    help = 'Idempotent link of R000016 bank accounts to Bobby/Mohit contacts'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry = bool(options.get('dry_run'))
        updated = 0
        skipped = 0
        for bank_id, contact_id, acct_no, phone in LINKS:
            bank = BankAccount.objects.filter(pk=bank_id, user_id=OWNER_USER_ID).first()
            contact = Contact.objects.filter(pk=contact_id, user_id=OWNER_USER_ID).first()
            if not bank or not contact:
                self.stderr.write(
                    self.style.ERROR(
                        f'Missing bank={bank_id} or contact={contact_id} for user {OWNER_USER_ID}'
                    )
                )
                continue
            if str(bank.account_number) != acct_no:
                self.stderr.write(
                    self.style.ERROR(
                        f'Bank {bank_id} account_number mismatch: {bank.account_number} != {acct_no}'
                    )
                )
                continue
            if str(contact.phone) != phone:
                self.stderr.write(
                    self.style.ERROR(
                        f'Contact {contact_id} phone mismatch: {contact.phone} != {phone}'
                    )
                )
                continue
            if bank.contact_id == contact_id:
                skipped += 1
                self.stdout.write(f'Already linked bank {bank_id} → contact {contact_id}')
                continue
            self.stdout.write(
                f'{"DRY-RUN " if dry else ""}Link bank {bank_id} ({acct_no}) → '
                f'contact {contact_id} ({contact.name} / {phone})'
            )
            if not dry:
                bank.contact = contact
                bank.save(update_fields=['contact', 'updated_at'])
                updated += 1
        self.stdout.write(
            self.style.SUCCESS(f'Done. updated={updated} skipped={skipped} dry_run={dry}')
        )
