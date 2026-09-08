# mPayHub Backend (Django REST API)

Django 4.2 + DRF service that powers authentication, users/hierarchy, wallets, fund management, BBPS, AEPS, reports, admin panel, and integrations.

Parent overview: [../README.md](../README.md)

---

## Requirements

| Need | Notes |
|------|--------|
| Python 3.10+ | 3.11 recommended |
| PostgreSQL 14+ | Or `USE_SQLITE=True` for local smoke only |
| Redis | When `REDIS_URL` is set (sessions, cache, rate limits) |
| pip + venv | Always use a virtualenv |

### Install which file?

```bash
# Local development (recommended)
pip install -r requirements.txt          # → requirements-dev.txt

# Explicit
pip install -r requirements-dev.txt      # prod + pytest/black/flake8/…
pip install -r requirements-prod.txt     # VPS / Gunicorn only
```

There is **no** frontend `requirements.txt`. UI deps are npm (`../frontend/package.json`).

---

## Quick start

```bash
cd backend
python3 -m venv venv
source venv/bin/activate                 # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
# Edit SECRET_KEY, DATABASE_URL (or USE_SQLITE=True), REDIS_URL, crypto keys

python manage.py migrate
python manage.py seed_module_permissions
python manage.py runserver               # http://127.0.0.1:8000
```

| URL | Purpose |
|-----|---------|
| `/api/health/` | Liveness |
| `/api/docs/` | Swagger UI (drf-spectacular) |
| `/api/schema/` | OpenAPI schema |
| `/django-admin/` | Django admin (staff users) |

UAT/prod process manager uses [`run_gunicorn.sh`](run_gunicorn.sh) → **`127.0.0.1:8002`** (not 8000).

---

## First accounts

```bash
# Admin operator (role Admin) — Django createsuperuser
python manage.py createsuperuser

# Super Admin (vendor) — dedicated command; does not replace createsuperuser
python manage.py create_super_admin \
  --phone 98XXXXXXXX \
  --email ops@example.com \
  --password 'StrongPasswordHere'
```

Operators (Admin / Super Admin) have optional KYC in the portal. Channel users still require KYC + MPIN before `account_ready`.

---

## Environment (`.env`)

Copy from [`.env.example`](.env.example). Comments must be on their **own lines** (python-decouple).

| Group | Examples |
|-------|----------|
| Django | `DJANGO_ENV`, `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` |
| Crypto | `MPIN_ENCRYPTION_KEY`, `INTEGRATION_SECRET_KEY` (do not rotate casually on live DB) |
| Database | `DATABASE_URL` or `DB_*`, `USE_SQLITE` |
| Redis | `REDIS_URL` |
| CORS | `CORS_ALLOWED_ORIGINS`, `CORS_ALLOW_ALL_ORIGINS` |
| S3 media | `USE_S3`, `AWS_*`, `AWS_S3_MEDIA_PREFIX` (`uat` / `prod`) |
| Integrations | Razorpay/PayU/SMS placeholders; BillAvenue WK/IV live **in DB**, not `.env` |

UAT vs prod: **same code**, different `.env` (DB name, hosts, CORS, S3 prefix).

After changing `.env` under PM2:

```bash
pm2 restart mpayhub-backend --update-env
```

---

## Django apps (`apps/`)

| App | Responsibility |
|-----|----------------|
| `authentication` | Login, JWT, MPIN, onboarding OTP, User model |
| `users` | Profiles, KYC, hierarchy, promote/demote |
| `core` | Roles helpers, permissions, maintenance, portal access, RBAC modules, media |
| `wallets` | Main / commission / BBPS wallets |
| `fund_management` | Pay-in packages, QR, payouts |
| `transactions` | Ledgers, reports, passbook |
| `bbps` | BillAvenue catalog, pay, admin console |
| `aeps` | Fingpay AEPS |
| `admin_panel` | Announcements, gateways, SMTP/SMS, appearance APIs |
| `integrations` | API Master, KYC providers, banking |
| `notifications` | Email/SMS dispatch |
| `session_security` | Single session, activity audit |
| `wallet_adjustments` | Admin wallet adjustments |
| `contacts` / `bank_accounts` | User contact & bank data |

### Folder conventions (per app)

Prefer:

```text
apps/<name>/
  models.py | models/
  serializers.py
  services.py | services/
  views.py | views/
  urls.py
  permissions.py   # when app-specific
  tests/
  management/commands/
```

Business rules belong in **services**, not fat views. Shared role checks use `apps.core.roles` (`is_platform_operator`, `is_super_admin`).

---

## Useful management commands

| Command | Purpose |
|---------|---------|
| `migrate` | Apply DB migrations |
| `createsuperuser` | Create **Admin** staff user |
| `create_super_admin` | Create **Super Admin** |
| `seed_module_permissions` | Seed AppModule / RoleModulePermission |
| `sync_local_media_to_s3` | Upload local `media/` gaps to S3 (also on Gunicorn start when `USE_S3=True`) |
| `verify_media_storage` | Spot-check media backend |
| `warmup_bbps_catalog` | BBPS catalog warm (also on Gunicorn start) |

---

## Production / UAT process

```bash
# From backend/ (PM2 runs this script)
./run_gunicorn.sh
# → sync_local_media_to_s3 (best-effort)
# → warmup_bbps_catalog (best-effort)
# → gunicorn bind 127.0.0.1:8002
```

Do **not** use deprecated `run_gunicorn_uat.sh` (old port `8001`).

---

## Tests

```bash
source venv/bin/activate
# Prefer pytest when available:
pytest
# or:
python manage.py test apps.users.tests
```

Use a dedicated test database; do not point tests at production `DATABASE_URL`.

---

## API layout (prefix `/api/`)

Mounted from `config/urls.py`, including:

- `/api/auth/` — login, me, onboarding, permissions
- `/api/users/` — directory, KYC, role change
- `/api/wallets/`, `/api/fund-management/`, `/api/transactions/`, `/api/reports/`
- `/api/bbps/`, `/api/aeps/`, `/api/admin/`, `/api/system/`

---

## Related

- Deploy / nginx / S3: [../deploy/README.md](../deploy/README.md)
- Security: [../SECURITY.md](../SECURITY.md)
- Contributing: [../CONTRIBUTING.md](../CONTRIBUTING.md)
