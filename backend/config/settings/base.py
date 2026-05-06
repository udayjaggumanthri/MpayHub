"""
Base settings for mPayhub project.
"""

from pathlib import Path
from decimal import Decimal
from decouple import config
import logging
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
_SETTINGS_LOG = logging.getLogger(__name__)
_SECRET_KEY_INSECURE_DEFAULT = 'django-insecure-change-this-in-production'
SECRET_KEY = config('SECRET_KEY', default=_SECRET_KEY_INSECURE_DEFAULT)
if SECRET_KEY == _SECRET_KEY_INSECURE_DEFAULT:
    _SETTINGS_LOG.warning(
        'SECRET_KEY is using the insecure default. Set a strong unique value before production; '
        'production settings refuse to start with this default.'
    )


def get_csv_setting(name, default=''):
    """
    Parse comma-separated env vars into a clean list.
    """
    raw_value = config(name, default=default)
    return [item.strip() for item in raw_value.split(',') if item.strip()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    # Note: apps.authentication must come before django.contrib.auth
    # to ensure our custom createsuperuser command takes precedence
    'apps.authentication',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_ratelimit',
    'drf_spectacular',
    
    # Local apps
    'apps.core',
    'apps.users',
    'apps.wallets',
    'apps.fund_management',
    'apps.bbps',
    'apps.contacts',
    'apps.bank_accounts',
    'apps.transactions',
    'apps.admin_panel',
    'apps.integrations',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# Support both DATABASE_URL and individual DB settings
DATABASE_URL = config('DATABASE_URL', default=None)
if DATABASE_URL:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='mpayhub'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default='postgres'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'authentication.User'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.authentication.jwt_auth.ActiveUserJWTAuthentication',
        'apps.authentication.jwt_auth.ActiveUserSessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Per-scope rates for throttles declared on viewsets (e.g. contacts).
    'DEFAULT_THROTTLE_RATES': {
        'contacts': '180/min',
    },
}

# API Documentation Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'mPayhub API',
    'DESCRIPTION': 'Django REST Framework API for mPayhub payment platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# JWT Settings
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# CORS Settings (env-driven, with safe local defaults)
CORS_ALLOWED_ORIGINS = get_csv_setting(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000'
)
CORS_ALLOW_CREDENTIALS = config('CORS_ALLOW_CREDENTIALS', default=True, cast=bool)

# Cache (django-ratelimit / RATELIMIT_USE_CACHE). LocMem is fine for single-process dev.
# In production with multiple Gunicorn/uwsgi workers, rate limits are only accurate if all workers
# share one cache backend — configure REDIS_URL in production settings (see production.py).
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Rate Limiting
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

# MPIN: use MPIN_ENCRYPTION_KEY for a dedicated Fernet secret; if unset, MPIN crypto uses SHA256(SECRET_KEY) (legacy).
# ENCRYPTION_KEY is kept for other features / docs; it is not used to encrypt new MPINs (avoids breaking existing DB rows).
ENCRYPTION_KEY = config('ENCRYPTION_KEY', default='')
MPIN_ENCRYPTION_KEY = config('MPIN_ENCRYPTION_KEY', default='')
INTEGRATION_SECRET_KEY = config('INTEGRATION_SECRET_KEY', default=SECRET_KEY)

# OTP Settings
OTP_EXPIRY_MINUTES = 5
OTP_LENGTH = 6

# Wallet Settings
WALLET_TYPES = ['main', 'commission', 'bbps']

# Pay-in: optional Django user id (pk) who receives 100% of platform gateway + admin shares (commission wallet).
# If unset/invalid: split those amounts evenly across every active Admin; if no Admin users, first superuser gets 100%.
def _optional_positive_int(name: str):
    raw = config(name, default='')
    if raw is None or str(raw).strip() == '':
        return None
    try:
        v = int(str(raw).strip())
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


PLATFORM_PAYIN_SETTLEMENT_USER_ID = _optional_positive_int('PLATFORM_PAYIN_SETTLEMENT_USER_ID')

# Service Charge Settings
BBPS_SERVICE_CHARGE = config('BBPS_SERVICE_CHARGE', default=5.00, cast=float)
BBPS_PROVIDER_GOVERNANCE_ENABLED = config('BBPS_PROVIDER_GOVERNANCE_ENABLED', default=True, cast=bool)
BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED = config('BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED', default=False, cast=bool)
BBPS_AUTO_PULL_PLANS_ON_SYNC = config('BBPS_AUTO_PULL_PLANS_ON_SYNC', default=True, cast=bool)
BBPS_AUTO_PULL_PLANS_MAX_BILLERS = config('BBPS_AUTO_PULL_PLANS_MAX_BILLERS', default=50, cast=int)
# Assisted credit-card / loan mapping strategy:
# - mdm_strict (default): do not synthesize Cash; use only MDM-listed payment modes.
# - agt_cash_when_eligible: legacy fallback for AGT+Cash where business wants forced assisted counter mode.
BBPS_ASSISTED_CARD_PAYMENT_UI = config('BBPS_ASSISTED_CARD_PAYMENT_UI', default='mdm_strict')
BANK_VERIFICATION_CHARGE = config('BANK_VERIFICATION_CHARGE', default=3.00, cast=float)

# Payout slab (addition model): amount ≤ PAYOUT_SLAB_LOW_MAX → low charge; else high charge
PAYOUT_SLAB_LOW_MAX = Decimal(str(config('PAYOUT_SLAB_LOW_MAX', default='24999')))
PAYOUT_CHARGE_LOW = Decimal(str(config('PAYOUT_CHARGE_LOW', default='7')))
PAYOUT_CHARGE_HIGH = Decimal(str(config('PAYOUT_CHARGE_HIGH', default='15')))

# Razorpay (pay-in). Leave blank to use mock / manual complete only.
RAZORPAY_KEY_ID = config('RAZORPAY_KEY_ID', default='')
RAZORPAY_KEY_SECRET = config('RAZORPAY_KEY_SECRET', default='')
# Webhook signing secret from Dashboard → Webhooks (not the same as KEY_SECRET); required for /api/integrations/razorpay/webhook/
RAZORPAY_WEBHOOK_SECRET = config('RAZORPAY_WEBHOOK_SECRET', default='')

# PayU (optional; order + webhook to be extended)
PAYU_MERCHANT_KEY = config('PAYU_MERCHANT_KEY', default='')
PAYU_MERCHANT_SALT = config('PAYU_MERCHANT_SALT', default='')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
