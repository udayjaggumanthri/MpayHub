"""
Script to create .env file with database configuration.
"""
import os
from pathlib import Path

# Get the backend directory
BASE_DIR = Path(__file__).resolve().parent.parent

# .env file content
env_content = """# Django Settings
DJANGO_ENV=development
SECRET_KEY=django-insecure-change-this-to-a-secure-key-in-production-min-50-chars
DEBUG=True

# Database Configuration - Using DATABASE_URL
DATABASE_URL=postgresql://postgres:StrongPass%40123@localhost:5432/mpayhub

# Alternative: Individual Database Settings (if not using DATABASE_URL)
# DB_NAME=mpayhub
# DB_USER=postgres
# DB_PASSWORD=StrongPass@123
# DB_HOST=localhost
# DB_PORT=5432
USE_SQLITE=False

# Encryption Key (32 characters - change this in production)
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

# Write .env file
env_file = BASE_DIR / '.env'
with open(env_file, 'w') as f:
    f.write(env_content)

print(f".env file created successfully at {env_file}")
print("\nNote: The .env file contains your database credentials.")
print("Make sure it's in your .gitignore (it should be by default).")
