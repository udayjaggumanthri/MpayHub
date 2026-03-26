"""
Database setup script.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.core.management import execute_from_command_line

if __name__ == '__main__':
    execute_from_command_line(['manage.py', 'migrate'])
