"""
Django settings for mPayhub project.
"""

from decouple import config
import os

# Determine the environment
ENVIRONMENT = config('DJANGO_ENV', default='development')

if ENVIRONMENT == 'production':
    from .production import *
elif ENVIRONMENT == 'testing':
    from .testing import *
else:
    from .development import *
