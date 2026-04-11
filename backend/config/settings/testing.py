"""
Testing settings for mPayhub project.
"""

from copy import deepcopy

from .base import *

# Avoid flaky contact API tests from per-user throttles (production rates stay in base).
REST_FRAMEWORK = deepcopy(REST_FRAMEWORK)
REST_FRAMEWORK.setdefault('DEFAULT_THROTTLE_RATES', {})['contacts'] = '100000/min'

# Use in-memory database for faster tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Disable migrations during tests for speed
class DisableMigrations:
    def __contains__(self, item):
        return True
    
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Password hashing - Use faster algorithm for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable rate limiting in tests
RATELIMIT_ENABLE = False

# Email backend
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
