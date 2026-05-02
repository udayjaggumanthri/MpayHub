"""
Development settings for mPayhub project.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = [
    'partner.mpayhub.in',
    '57.131.39.21',
    'localhost',
    '127.0.0.1'
]

# Database - Can use SQLite for development if PostgreSQL is not available
USE_SQLITE = config('USE_SQLITE', default=False, cast=bool)

if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# CORS in development (defaults keep existing behavior)
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=True, cast=bool)

# Email Backend (Console for development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Add development-specific apps
INSTALLED_APPS += [
    # 'django_extensions',  # Uncomment if needed: pip install django-extensions
]

# Disable rate limiting in development (optional)
RATELIMIT_ENABLE = False
# Note: django-ratelimit validates cache backend even when disabled
# The cache warnings can be ignored in development since rate limiting is disabled
# For production, use Redis or Memcached which support atomic operations
RATELIMIT_USE_CACHE = 'default'
