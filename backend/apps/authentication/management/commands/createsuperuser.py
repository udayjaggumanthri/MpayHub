"""
Custom createsuperuser command that uses phone instead of username.
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.core.utils import generate_user_id

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
        mpin = None  # Initialize mpin variable

        # Validate that phone is provided if not interactive
        if not interactive:
            if not phone:
                raise CommandError('You must use --phone with --noinput.')
            if not email:
                raise CommandError('You must use --email with --noinput.')

        # Get user model
        User = get_user_model()
        db_manager = User._default_manager.db_manager(database)

        # Interactive mode
        if interactive:
            try:
                # Get phone
                if not phone:
                    phone = input('Phone: ')
                    if not phone:
                        raise CommandError('Superuser creation cancelled.')

                # Get email
                if not email:
                    email = input('Email: ')
                    if not email:
                        raise CommandError('Superuser creation cancelled.')

                # Get password
                import getpass
                password = getpass.getpass('Password: ')
                password_again = getpass.getpass('Password (again): ')
                if password != password_again:
                    raise CommandError('Passwords do not match.')
                if not password:
                    raise CommandError('Password cannot be blank.')

                # Get MPIN (mandatory)
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

        # Non-interactive mode
        else:
            # In non-interactive mode, we need to generate a password or require it
            # For security, we'll require it to be set via environment variable or fail
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

        # Validate phone and email
        if db_manager.filter(phone=phone).exists():
            raise CommandError(f'Error: That phone number "{phone}" is already taken.')
        if db_manager.filter(email=email).exists():
            raise CommandError(f'Error: That email "{email}" is already taken.')

        # Create superuser
        try:
            with transaction.atomic(using=database):
                # Generate user_id
                existing_user_ids = list(User.objects.filter(role='Admin').values_list('user_id', flat=True))
                user_id = generate_user_id('Admin', existing_user_ids)
                
                # Create user
                user = db_manager.create_superuser(
                    phone=phone,
                    email=email,
                    password=password,
                    user_id=user_id,
                    role='Admin',
                    is_staff=True,
                    is_superuser=True,
                )
                
                # Set MPIN (mandatory)
                user.set_mpin(mpin)
                
                self.stdout.write(
                    self.style.SUCCESS(f'Superuser created successfully with phone: {phone}')
                )
                self.stdout.write(
                    self.style.SUCCESS(f'MPIN has been set for the superuser.')
                )
        except Exception as e:
            raise CommandError(f'Error creating superuser: {str(e)}')
