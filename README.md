# mPayHub

Monorepo for the mPayHub platform:
- `backend/`: Django REST API
- `frontend/`: React web application

This guide covers local development, GitHub push readiness, and VPS deployment basics.

## Tech Stack

- Backend: Python, Django, Django REST Framework, PostgreSQL
- Frontend: React (CRA), Tailwind CSS, Axios
- API Auth: JWT (SimpleJWT)

## Repository Structure

```text
mPayHub/
  backend/
  frontend/
  Resource/
  INTEGRATION_SUMMARY.md
  INTEGRATION_TEST_SUMMARY.md
  TEST_RESULTS.md
```

## Prerequisites

- Python 3.10+ (3.11 recommended)
- Node.js 18+ and npm
- PostgreSQL 14+ (or SQLite for local-only backend testing)
- Git

## 1) Backend Setup

```bash
cd backend
python -m venv venv
```

Activate virtual environment:
- Windows (PowerShell): `.\venv\Scripts\Activate.ps1`
- Windows (CMD): `venv\Scripts\activate.bat`
- Linux/macOS: `source venv/bin/activate`

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Note: backend uses a single dependency file (`backend/requirements.txt`) for development, testing, and production.

Create environment file:

```bash
copy .env.example .env
```

Update `.env` values (DB, secret key, API keys, etc.), then run:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Backend base URL: `http://127.0.0.1:8000`

## 2) Frontend Setup

```bash
cd frontend
npm install
```

Create environment file:

```bash
copy .env.example .env
```

Run frontend:

```bash
npm start
```

Frontend URL: `http://localhost:3000`

## 3) Running Tests

Backend:

```bash
cd backend
pytest
```

Frontend:

```bash
cd frontend
npm test
```

## 4) Production Build

Frontend:

```bash
cd frontend
npm run build
```

Backend dependencies:

```bash
cd backend
pip install -r requirements.txt
```

## 5) VPS Deployment (High Level)

1. Provision Ubuntu VPS (recommended), install Python, Node, PostgreSQL, Nginx.
2. Clone repo and create backend `.env` from `.env.example`.
3. Install backend production requirements and run migrations.
4. Build frontend (`npm run build`).
5. Serve Django with Gunicorn behind Nginx.
6. Configure HTTPS (Let's Encrypt).
7. Enable process management with `systemd`.

## 6) GitHub Push Checklist

Before pushing:
- Ensure `.env` files are not committed.
- Ensure `backend/venv` and `frontend/node_modules` are not tracked.
- Confirm secrets are removed from tracked files.
- Commit only source code, docs, and safe config templates.

## Additional Documentation

- Backend details: `backend/README.md`
- Frontend details: `frontend/README.md`
- Integration notes: `INTEGRATION_SUMMARY.md`, `INTEGRATION_TEST_SUMMARY.md`
