# Contributing to mPayHub

Thank you for helping maintain mPayHub. This guide is for team developers working in this monorepo.

---

## Before you start

1. Read [README.md](README.md) (product overview + local quick start).
2. Read [SECURITY.md](SECURITY.md) (secrets and operator roles).
3. Use a **feature branch** off the shared main line your team uses (`main` / agreed default).
4. Never commit `.env`, dumps, AWS keys, or customer data.

---

## Local checklist

```bash
# Backend
cd backend && source venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py check

# Frontend
cd frontend
npm ci --legacy-peer-deps   # or npm install
npm start                   # against local API or /api via proxy
```

Before opening a PR / handing off:

- [ ] Migrations included if models changed (`makemigrations` reviewed)
- [ ] No secrets in the diff
- [ ] Backend smoke: `/api/health/`
- [ ] Frontend builds if you touched UI: `npm run build`
- [ ] Role-sensitive changes tested as Admin **and** Super Admin when relevant

---

## Where to put new code

### Backend (`backend/apps/<app>/`)

| Kind | Place |
|------|--------|
| Domain logic | `services.py` / `services/` |
| HTTP | `views.py` + `serializers.py` + `urls.py` |
| Shared roles | `apps.core.roles` — avoid new `role == 'Admin'` copies |
| Permissions | Prefer existing `IsAdmin` / `IsSuperAdmin` / module checks |
| One-off ops | `management/commands/` |

New Django app: register in `config/settings` `INSTALLED_APPS` and wire URLs in `config/urls.py`.

### Frontend (`frontend/src/`)

| Kind | Place |
|------|--------|
| Screens | `components/<domain>/` or `modules/<feature>/` |
| Routes | `routes/AppRoutes.jsx` |
| API calls | `services/api.js` (or module API wrappers) |
| Menus / role helpers | `utils/rolePermissions.js` |

Match existing admin UI patterns (Maintenance, User Management). Prefer grouping under **Platform settings** for operator tools.

---

## Dependency changes

| Stack | File to update |
|-------|----------------|
| Python runtime | `backend/requirements-prod.txt` (+ note in `requirements-dev.txt` if tooling) |
| Node | `frontend/package.json` + commit lockfile |
| Locust | `loadtest/requirements.txt` |

Do not add a Python `requirements.txt` under `frontend/`.

---

## Pull requests

- Prefer small, reviewable PRs (one concern per PR when possible).
- Describe **why**, not only what.
- Call out migrations, env var additions, and deploy steps (rebuild SPA, `pm2 restart … --update-env`).
- UAT first when touching money, KYC, or auth.

---

## What not to change casually

- `MPIN_ENCRYPTION_KEY` / `INTEGRATION_SECRET_KEY` on a live DB (breaks existing ciphertext).
- Financial access rules for operators without product sign-off.
- Production `DATABASE_URL` from a laptop.

---

## Docs

If you change how to run or deploy the app, update the matching README (`backend/`, `frontend/`, `deploy/`) in the same PR.
