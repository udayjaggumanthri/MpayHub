"""
Development settings for mPayhub project.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)
# Prefer ALLOWED_HOSTS from .env (comma-separated). Use * to allow all.
_allowed = config(
    'ALLOWED_HOSTS',
    default='partner-uat.mpayhub.in,partner.mpayhub.in,57.131.39.21,localhost,127.0.0.1,139.99.47.143',
)
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(',') if h.strip()]

_csrf = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://partner-uat.mpayhub.in,https://partner.mpayhub.in',
)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf.split(',') if o.strip()]

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
