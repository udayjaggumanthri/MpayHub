"""
Testing settings for mPayhub project.
"""

from .base import *

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
