"""
Development settings for mPayhub project.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Database - Can use SQLite for development if PostgreSQL is not available
from decouple import config

USE_SQLITE = config('USE_SQLITE', default=False, cast=bool)

if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# CORS - Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

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