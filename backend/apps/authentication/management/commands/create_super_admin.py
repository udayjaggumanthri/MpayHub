"""
Create a Super Admin operator account (does not replace createsuperuser / Admin).
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.authentication.models import User
from apps.core.roles import ROLE_SUPER_ADMIN
from apps.users.identity import assign_identity_fields
from apps.users.models import KYC, UserProfile
from apps.wallets.models import Wallet


class Command(BaseCommand):
    help = 'Create a Super Admin user (phone + email + password).'

    def add_arguments(self, parser):
        parser.add_argument('--phone', required=True, help='10-digit login phone')
        parser.add_argument('--email', required=True, help='Unique email')
        parser.add_argument('--password', required=True, help='Login password')
        parser.add_argument('--first-name', default='Super', dest='first_name')
        parser.add_argument('--last-name', default='Admin', dest='last_name')

    @transaction.atomic
    def handle(self, *args, **options):
        phone = str(options['phone']).strip()
        email = str(options['email']).strip().lower()
        password = options['password']
        if len(phone) != 10 or not phone.isdigit():
            raise CommandError('phone must be a 10-digit number')
        if User.objects.filter(phone=phone).exists():
            raise CommandError(f'User with phone {phone} already exists')
        if User.objects.filter(email=email).exists():
            raise CommandError(f'User with email {email} already exists')

        user = User(
            phone=phone,
            email=email,
            first_name=options['first_name'],
            last_name=options['last_name'],
            role=ROLE_SUPER_ADMIN,
            is_staff=True,
            is_superuser=True,
            is_active=True,
            must_change_password=False,
        )
        user.set_password(password)
        assign_identity_fields(user, role=ROLE_SUPER_ADMIN)
        user.save()

        UserProfile.objects.get_or_create(user=user)
        KYC.objects.get_or_create(user=user)
        for wallet_type in ('main', 'commission', 'bbps'):
            Wallet.objects.get_or_create(user=user, wallet_type=wallet_type, defaults={'balance': 0})

        self.stdout.write(
            self.style.SUCCESS(
                f'Super Admin created: phone={phone} display_code={user.display_code} id={user.pk}'
            )
        )
