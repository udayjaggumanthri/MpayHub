# mPayHub Backend API

Django REST Framework backend for the mPayHub payment platform.

## Requirements

- Python 3.10+ (3.11 recommended)
- PostgreSQL 14+ (recommended for normal development)
- pip

## Quick Start

1) Create and activate virtual environment:

```bash
python -m venv venv
```

Activation:
- Windows (PowerShell): `.\venv\Scripts\Activate.ps1`
- Windows (CMD): `venv\Scripts\activate.bat`
- Linux/macOS: `source venv/bin/activate`

2) Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

3) Create env file:

```bash
copy .env.example .env
```

4) Update `.env` values for your machine (database credentials, secret key, external keys).

5) Run database migrations:

```bash
python manage.py migrate
```

6) Create superuser:

```bash
python manage.py createsuperuser
```

7) Start development server:

```bash
python manage.py runserver
```

Backend URL: `http://127.0.0.1:8000`

## Dependency Management

| File | Use |
|------|-----|
| `requirements-prod.txt` | **Production VPS** — Django, Gunicorn, Redis client, Postgres, integrations |
| `requirements-dev.txt` | Local dev — prod deps + pytest, lint, debug toolbar |
| `requirements.txt` | Alias for `requirements-dev.txt` (backward compatible) |

Production install:

```bash
pip install -r requirements-prod.txt
```

Local / CI install:

```bash
pip install -r requirements-dev.txt
```

When `REDIS_URL` is set in `.env`, install and run **redis-server** on the host (login/session/cache depend on it).

## Environment Variables

See `.env.example` for all supported variables.

Important:
- `DJANGO_ENV=development|production|testing`
- `DATABASE_URL` or individual `DB_*` values
- `SECRET_KEY` and `ENCRYPTION_KEY`
- External API credentials for BBPS/payment/SMS/bank verification

## Running Tests

```bash
pytest
```

## API Documentation

After server start:
- OpenAPI schema: `http://127.0.0.1:8000/api/schema/`
- Swagger docs: `http://127.0.0.1:8000/api/docs/`

## Production Notes

Install dependencies:

```bash
pip install -r requirements-prod.txt
```

Use:
- `DJANGO_ENV=production`
- Gunicorn behind Nginx
- HTTPS and secure env values

## Project Structure

- `apps/`: domain apps
- `config/`: project settings and URL config
- `tests/`: additional tests
- `scripts/`: helper scripts
