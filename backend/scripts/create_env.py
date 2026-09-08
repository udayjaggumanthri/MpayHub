"""
Helper to create a starter backend/.env from placeholders.

Prefer copying .env.example instead:
  cp .env.example .env

This script never embeds real passwords. Edit .env after generation.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

env_content = """# Django Settings
DJANGO_ENV=development
SECRET_KEY=django-insecure-change-this-to-a-secure-key-in-production-min-50-chars
DEBUG=True

# Database — use placeholders only; copy real values from your secrets store
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/mpayhub

# Alternative: Individual Database Settings (if not using DATABASE_URL)
# DB_NAME=mpayhub
# DB_USER=postgres
# DB_PASSWORD=postgres
# DB_HOST=127.0.0.1
# DB_PORT=5432
USE_SQLITE=False

# Encryption Key (change in production; see .env.example for MPIN / INTEGRATION keys)
ENCRYPTION_KEY=your-32-character-encryption-key-here-change-in-production

# CORS Settings
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Email Configuration (Production)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# External API Keys (Add your actual keys when ready)
BBPS_API_KEY=your-bbps-api-key
BBPS_API_URL=https://api.bbps.example.com

# Payment Gateway Keys
RAZORPAY_KEY_ID=your-razorpay-key
RAZORPAY_KEY_SECRET=your-razorpay-secret

# SMS Service
SMS_API_KEY=your-sms-api-key
SMS_API_URL=https://api.sms.example.com
SMS_PROVIDER=console

# Bank Validation API
BANK_VALIDATION_API_KEY=your-bank-validation-key
BANK_VALIDATION_API_URL=https://api.bank-validation.example.com
"""

env_file = BASE_DIR / '.env'
if env_file.exists():
    raise SystemExit(f'{env_file} already exists — refuse to overwrite. Edit it or remove it first.')

env_file.write_text(env_content)
print(f'.env file created at {env_file}')
print('Prefer maintaining secrets via .env.example + your password manager.')
print('Ensure .env stays gitignored.')
