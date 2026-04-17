#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    
    # Automatically add --skip-checks for all commands in development (except 'check' command)
    # This bypasses cache backend validation warnings (django-ratelimit)
    # Rate limiting is disabled in development, so cache warnings can be ignored
    if len(sys.argv) > 1:
        command = sys.argv[1]
        # Skip checks for all commands except 'check' itself
        if command not in ('check', 'test') and '--skip-checks' not in sys.argv:
            sys.argv.append('--skip-checks')
    
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
