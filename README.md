# mPayHub

Partner portal for digital payments and channel distribution: pay-in, payout, BBPS, AEPS, wallets, commissions, and platform administration.

This monorepo is the single source of truth for **UAT** and **production**. Same application code; environment differences live only in `.env` (and deploy hosts).

| Document | Purpose |
|----------|---------|
| [backend/README.md](backend/README.md) | Django API setup, apps, commands, env |
| [frontend/README.md](frontend/README.md) | React SPA setup, build, env |
| [deploy/README.md](deploy/README.md) | nginx, PM2, ports, S3 media |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to work in this repo |
| [SECURITY.md](SECURITY.md) | Secrets, roles, reporting |
| [docs/LOAD_TEST_GUIDE.md](docs/LOAD_TEST_GUIDE.md) | Locust load testing |

---

## Product overview

mPayHub serves two kinds of users on one portal:

1. **Platform operators** — Super Admin (vendor) and Admin (client operator). They manage users, reports, gateways, BBPS/AEPS settings, maintenance, appearance, and (Super Admin) roles matrix + test usage mode. They do **not** use agent money flows (pay-in / payout / BBPS as an agent).
2. **Channel roles** — Super Distributor → Master Distributor → Distributor → Retailer. They onboard downline, complete KYC/MPIN, and run transactions according to hierarchy and packages.

```text
Super Admin  (vendor / break-glass)
    └── Admin  (client operator)
            └── Super Distributor → Master Distributor → Distributor → Retailer
```

Business data (users, wallets, commissions, reports) lives in the **shared platform database**. Changing an Admin’s password or replacing an Admin user does **not** wipe history.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| API | Python 3.10+, Django 4.2, Django REST Framework, SimpleJWT |
| UI | React (Create React App), Tailwind CSS, Axios |
| Data | PostgreSQL 14+ (SQLite optional for local smoke only) |
| Cache / sessions | Redis (required when `REDIS_URL` is set) |
| Process | Gunicorn (API), `serve` (built SPA), PM2 |
| Edge | nginx (`/`, `/api/`, `/media/`) |
| Media | Local disk or private S3 (`USE_S3`) via django-storages |

---

## Repository structure

```text
MpayHub/
  README.md                 # this file
  CONTRIBUTING.md
  SECURITY.md
  ecosystem.config.cjs      # PM2: API :8002, SPA :3002
  backend/                  # Django project (config/ + apps/)
  frontend/                 # React SPA (src/)
  deploy/                   # nginx configs + deploy notes
  scripts/                  # PM2 / domain / media helpers
  docs/                     # operational guides (load test, …)
  loadtest/                 # Locust (optional)
```

Backend apps live under `backend/apps/` (`authentication`, `users`, `wallets`, `fund_management`, `bbps`, `aeps`, `transactions`, `admin_panel`, `integrations`, `notifications`, `session_security`, `wallet_adjustments`, `core`, …).

---

## Prerequisites

- **Python** 3.10+ (3.11 recommended)
- **Node.js** 18+ and **npm** 9+
- **PostgreSQL** 14+ (or `USE_SQLITE=True` for a quick local API smoke)
- **Redis** for production-like login/session behavior
- **Git**

---

## Quick start (local development)

Use two terminals. Paths assume you are at the repo root.

### 1) Backend API (`http://127.0.0.1:8000`)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt   # = requirements-dev (tests + lint)

cp .env.example .env
# Edit .env: SECRET_KEY, DATABASE_URL (or USE_SQLITE=True), REDIS_URL if available

python manage.py migrate
python manage.py seed_module_permissions
python manage.py runserver
```

API health: `http://127.0.0.1:8000/api/health/`  
OpenAPI UI: `http://127.0.0.1:8000/api/docs/`

### 2) Frontend SPA (`http://localhost:3000`)

```bash
cd frontend
cp .env.example .env
# Local against runserver:
#   REACT_APP_API_BASE_URL=http://127.0.0.1:8000/api
# UAT/prod builds use same-origin:
#   REACT_APP_API_BASE_URL=/api

npm install
# or: npm ci --legacy-peer-deps
npm start
```

---

## First operators (after migrate)

### Create a classic Admin (Django `createsuperuser`)

Still creates role **Admin** (client operator bootstrap):

```bash
cd backend && source venv/bin/activate
python manage.py createsuperuser
# prompts: phone, email, password → role Admin, is_staff=True
```

### Create a Super Admin (vendor)

```bash
cd backend && source venv/bin/activate
python manage.py create_super_admin \
  --phone 98XXXXXXXX \
  --email you@example.com \
  --password 'ChooseAStrongPassword'
```

Do **not** promote a live production Admin to Super Admin unless you intentionally choose that. Prefer the command on UAT first.

### Seed module permissions (RBAC matrix)

```bash
python manage.py seed_module_permissions
```

Idempotent. Super Admin can edit the matrix in the UI under **Platform settings → Roles & permissions**.

---

## Dependency files (what to install where)

| File | Who uses it |
|------|-------------|
| [`backend/requirements-prod.txt`](backend/requirements-prod.txt) | UAT / production VPS (Gunicorn) |
| [`backend/requirements-dev.txt`](backend/requirements-dev.txt) | Local developers (prod + pytest/black/…) |
| [`backend/requirements.txt`](backend/requirements.txt) | Alias → `requirements-dev.txt` |
| [`frontend/package.json`](frontend/package.json) | Frontend (npm) — **not** a Python requirements file |
| [`loadtest/requirements.txt`](loadtest/requirements.txt) | Locust only |

---

## UAT / production (high level)

Same code. Different `backend/.env` (database, hosts, CORS, S3 prefix).

| Process | Bind address |
|---------|----------------|
| API (Gunicorn via PM2) | `127.0.0.1:8002` |
| SPA (`serve` via PM2) | `127.0.0.1:3002` |
| Public | nginx `:80`/`:443` → `/`, `/api/`, `/media/` |

Details: [deploy/README.md](deploy/README.md). Frontend production builds must use `REACT_APP_API_BASE_URL=/api`.

---

## What never to commit

- `backend/.env`, `frontend/.env`, any `*.env.bak`
- Database dumps (`*.dump`, `backups/`)
- AWS / payment / SMS secrets
- `venv/`, `node_modules/`, `backend/media/` private uploads

See [SECURITY.md](SECURITY.md).

---

## Smoke checklist (new developer)

1. `GET /api/health/` returns OK  
2. Login as Admin and as Super Admin  
3. Admin **cannot** promote a user to Admin; Super Admin **can**  
4. Channel user still required to complete KYC before portal ready  
5. Operators skip hard KYC gate (`kyc_optional`)  
6. After `npm run build`, SPA loads behind nginx with `/api` same-origin  

---

## License / ownership

Internal mPayHub product. Do not publish secrets or customer data outside the team.
