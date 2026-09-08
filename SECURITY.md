# Security

Security practices for the mPayHub monorepo. This document does **not** change product behavior; it records how the team should handle secrets, roles, and known hygiene items.

---

## Report a concern

If you find a vulnerability, exposed secret, or suspicious access:

1. Do **not** post secrets in public tickets or chat.
2. Notify the platform owners / Super Admin contacts privately.
3. Rotate affected credentials after containment (DB password, AWS keys, `SECRET_KEY` only with a planned cutover).

---

## Secrets and configuration

| Safe to commit | Never commit |
|----------------|--------------|
| `.env.example` (placeholders) | `.env`, `.env.bak`, `.env.*` with real values |
| Docs with `your-key-here` | AWS keys, DB URLs with passwords, JWT/MPIN keys |
| nginx configs without private keys | Database dumps (`*.dump`), customer exports |

### Crypto keys (backend)

- **`SECRET_KEY`** — Django signing; strong random value in production.
- **`MPIN_ENCRYPTION_KEY`** — encrypts MPINs at rest. Rotating without re-encrypting locks users out.
- **`INTEGRATION_SECRET_KEY`** — decrypts BillAvenue / API Master / SMTP secrets stored in Postgres. Same rotation caution.

BillAvenue Working Key / IV and many integration passwords live **in the database** (encrypted), not in `.env`.

### Frontend

Only `REACT_APP_*` public config (e.g. `REACT_APP_API_BASE_URL=/api`). No server secrets in the SPA bundle.

---

## Roles and access

| Role | Notes |
|------|--------|
| Super Admin | Vendor / break-glass; Test usage mode; edit RBAC matrix; always bypasses Test usage login gate |
| Admin | Client operator; channel create/promote only; cannot see/edit Super Admins or promote to Admin |
| Channel roles | KYC + MPIN required; hierarchy-scoped data |

Operators are blocked from agent financial APIs (`FINANCIAL_TX_BLOCKED_ROLES`). Test usage mode restricts login to Super Admin + `is_test_user` accounts when enabled.

---

## Transport and edge

- Public traffic terminates at **nginx**; Gunicorn and `serve` bind **localhost only** (`8002` / `3002`).
- Prefer HTTPS at the edge; set `CSRF_TRUSTED_ORIGINS` and `ALLOWED_HOSTS` correctly.
- `/media/` may proxy to Django (local or private S3). Treat media as sensitive when it contains KYC/QR artifacts.

---

## Folder / repo hygiene (this pass)

Findings addressed or documented:

| Item | Status |
|------|--------|
| Tracked `backend/.env.bak` (could contain real DB URLs) | Stop tracking; ignore via `.gitignore` |
| Tracked `backups/*.dump` | Stop tracking; ignore dumps |
| Hardcoded DB password in `backend/scripts/create_env.py` | Replaced with placeholders |
| Live `backend/.env` on servers | Remains **gitignored**; never copy into git |
| No root `.gitignore` historically | Root `.gitignore` added for monorepo coverage |

If any secret was ever pushed to a remote, **rotate** it even after `git rm --cached`.

---

## Developer checklist

- [ ] `.env` exists only locally / on the server — not in PRs  
- [ ] New scripts read secrets from env, not hardcoded strings  
- [ ] Admin-only APIs use `IsAdmin` / `IsSuperAdmin` / module checks  
- [ ] Load tests prefer UAT; production stress only with approval ([docs/LOAD_TEST_GUIDE.md](docs/LOAD_TEST_GUIDE.md))  

---

## Related

- [README.md](README.md) — setup  
- [CONTRIBUTING.md](CONTRIBUTING.md) — workflow  
- [backend/.env.example](backend/.env.example) — env template  
