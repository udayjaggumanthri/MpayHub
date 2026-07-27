"""
Custom createsuperuser command that uses phone instead of username.
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.users.identity import assign_identity_fields

User = get_user_model()


class Command(BaseCommand):
    """
    Management command to create a superuser with phone number.
    """
    help = 'Used to create a superuser with phone number instead of username.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            dest='phone',
            default=None,
            help='Specifies the phone number for the superuser.',
        )
        parser.add_argument(
            '--email',
            dest='email',
            default=None,
            help='Specifies the email for the superuser.',
        )
        parser.add_argument(
            '--noinput', '--no-input',
            action='store_false', dest='interactive', default=True,
            help='Tells Django to NOT prompt the user for input of any kind.',
        )
        parser.add_argument(
            '--database',
            action='store', dest='database',
            default='default',
            help='Specifies the database to use. Default is "default".',
        )

    def handle(self, *args, **options):
        phone = options.get('phone')
        email = options.get('email')
        database = options.get('database')
        interactive = options.get('interactive')
        mpin = None

        if not interactive:
            if not phone:
                raise CommandError('You must use --phone with --noinput.')
            if not email:
                raise CommandError('You must use --email with --noinput.')

        User = get_user_model()
        db_manager = User._default_manager.db_manager(database)

        if interactive:
            try:
                if not phone:
                    phone = input('Phone: ')
                    if not phone:
                        raise CommandError('Superuser creation cancelled.')

                if not email:
                    email = input('Email: ')
                    if not email:
                        raise CommandError('Superuser creation cancelled.')

                import getpass
                password = getpass.getpass('Password: ')
                password_again = getpass.getpass('Password (again): ')
                if password != password_again:
                    raise CommandError('Passwords do not match.')
                if not password:
                    raise CommandError('Password cannot be blank.')

                mpin = getpass.getpass('MPIN (6 digits): ')
                if not mpin:
                    raise CommandError('MPIN is required and cannot be blank.')
                if len(mpin) != 6 or not mpin.isdigit():
                    raise CommandError('MPIN must be exactly 6 digits.')
                mpin_again = getpass.getpass('MPIN (again): ')
                if mpin != mpin_again:
                    raise CommandError('MPINs do not match.')

            except KeyboardInterrupt:
                self.stderr.write('\nOperation cancelled.')
                return

        else:
            import os
            password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
            if not password:
                raise CommandError(
                    'Password must be provided in non-interactive mode. '
                    'Set DJANGO_SUPERUSER_PASSWORD environment variable or use interactive mode.'
                )
            mpin = os.environ.get('DJANGO_SUPERUSER_MPIN')
            if not mpin:
                raise CommandError(
                    'MPIN must be provided in non-interactive mode. '
                    'Set DJANGO_SUPERUSER_MPIN environment variable (6 digits) or use interactive mode.'
                )
            if len(mpin) != 6 or not mpin.isdigit():
                raise CommandError('MPIN must be exactly 6 digits.')

        if db_manager.filter(phone=phone).exists():
            raise CommandError(f'Error: That phone number "{phone}" is already taken.')
        if db_manager.filter(email=email).exists():
            raise CommandError(f'Error: That email "{email}" is already taken.')

        try:
            with transaction.atomic(using=database):
                identity = assign_identity_fields(User(role='Admin'), role='Admin')
                user = db_manager.create_superuser(
                    phone=phone,
                    email=email,
                    password=password,
                    user_id=identity['member_id'],
                    member_number=identity['member_number'],
                    member_id=identity['member_id'],
                    display_code=identity['display_code'],
                    role='Admin',
                    is_staff=True,
                    is_superuser=True,
                )
                user.set_mpin(mpin)

                self.stdout.write(
                    self.style.SUCCESS(f'Superuser created successfully with phone: {phone}')
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Identity: {user.display_code} / {user.member_id}'
                    )
                )
        except Exception as e:
            raise CommandError(f'Error creating superuser: {str(e)}')
