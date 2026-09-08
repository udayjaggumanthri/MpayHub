# mPayHub Frontend (React SPA)

Create React App UI for the mPayHub partner portal (channel users + Admin / Super Admin).

Parent overview: [../README.md](../README.md)

> **Note:** Frontend dependencies use **npm** (`package.json`). There is no Python `requirements.txt` here.

---

## Requirements

- Node.js **18+**
- npm **9+** (lockfile: `package-lock.json`)

---

## Quick start

```bash
cd frontend
cp .env.example .env

# Against local Django runserver:
#   REACT_APP_API_BASE_URL=http://127.0.0.1:8000/api
#
# Against nginx / UAT / prod (same-origin — preferred):
#   REACT_APP_API_BASE_URL=/api

npm install
# CI / clean install:
# npm ci --legacy-peer-deps

npm start
```

Dev server: **http://localhost:3000**

---

## Environment

| Variable | Meaning |
|----------|---------|
| `REACT_APP_API_BASE_URL` | API prefix. UAT/prod builds must be `/api` so the browser calls the same host as the SPA. |

Only **public** config belongs here. Never put DB passwords, AWS keys, or MPIN encryption keys in frontend env.

After changing any `REACT_APP_*` value you must **rebuild**:

```bash
npm run build
pm2 restart mpayhub-frontend
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `npm start` | CRA dev server |
| `npm run build` | Production bundle → `build/` |
| `npm test` | CRA tests |
| `npm run ci:install` | `npm ci --legacy-peer-deps` |
| `npm run start:prod` | Serve `build/` (local helper; PM2 uses `serve` on **3002**) |

---

## Production serve (PM2)

[`../ecosystem.config.cjs`](../ecosystem.config.cjs) runs:

```text
serve -s build -l tcp://127.0.0.1:3002
```

nginx proxies `/` → `:3002`, `/api/` → Gunicorn `:8002`.

```bash
cd frontend
npm ci --legacy-peer-deps
npm run build
pm2 restart mpayhub-frontend
```

---

## Source layout

```text
src/
  components/       # UI by domain (auth, admin, reports, userManagement, …)
  context/          # Auth, appearance, …
  modules/          # Feature modules (e.g. aeps/)
  routes/           # AppRoutes.jsx
  services/         # api.js (Axios client + domain APIs)
  utils/            # rolePermissions.js, accessControl, onboardingPaths, …
  assets/
```

### Conventions for new UI

- Prefer existing admin styling (same patterns as Maintenance / User Management).
- Operator menus: [`src/utils/rolePermissions.js`](src/utils/rolePermissions.js) (`roleMenus`, Platform settings group).
- Gate admin pages with `AdminRoute` / `SuperAdminRoute`.
- Call the API only through [`src/services/api.js`](src/services/api.js) (or module APIs that wrap it).

---

## Roles in the UI (summary)

| Role | Menu notes |
|------|------------|
| Super Admin | Admin menus + Test usage under Platform settings |
| Admin | Platform settings without Test usage; cannot promote to Admin |
| Channel roles | Dashboard, products, reports, profile — no admin console |

Backend RBAC (`GET /api/auth/me/permissions/`) can filter sidebar modules; if the list is empty, hardcoded menus remain (no lockout).

---

## Related

- Backend API: [../backend/README.md](../backend/README.md)
- Deploy: [../deploy/README.md](../deploy/README.md)
- Contributing: [../CONTRIBUTING.md](../CONTRIBUTING.md)
