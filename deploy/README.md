# mPayHub Deploy

nginx + PM2 deployment notes for **production** (`partner.mpayhub.in`) and **UAT** (`partner-uat.mpayhub.in`).

**Rule:** same Git code on both environments. Only `backend/.env` (and host/nginx) differs.

Parent overview: [../README.md](../README.md)

---

## Architecture (current)

Both environments use the same process ports behind nginx:

| Component | PM2 app | Bind |
|-----------|---------|------|
| **API** | `mpayhub-backend` | `127.0.0.1:8002` ([`backend/run_gunicorn.sh`](../backend/run_gunicorn.sh)) |
| **UI** | `mpayhub-frontend` | `127.0.0.1:3002` (`serve -s build`) |
| **Edge** | nginx | `:80` / `:443` → `/` SPA, `/api/` API, `/media/` API |

Configured in [`../ecosystem.config.cjs`](../ecosystem.config.cjs).

```text
Internet → nginx
            ├─ /        → 127.0.0.1:3002
            ├─ /api/    → 127.0.0.1:8002
            └─ /media/  → 127.0.0.1:8002  (Django → local disk or S3)
```

Frontend production build **must** use:

```bash
REACT_APP_API_BASE_URL=/api
```

---

## UAT (partner-uat.mpayhub.in)

Repo path often: `/root/Mpayhub-UAT/MpayHub`. PM2 may run as root on this host.

| Item | Value |
|------|--------|
| Domain | `partner-uat.mpayhub.in` |
| DB | e.g. `…/uat2` in `DATABASE_URL` |
| S3 prefix | `AWS_S3_MEDIA_PREFIX=uat` when `USE_S3=True` |
| Tunnel | Cloudflare Tunnel may hit nginx on **`:3001`** → same vhost |

```bash
/root/Mpayhub-UAT/MpayHub/scripts/setup-uat-pm2-and-domain.sh
```

### UAT update

```bash
cd /root/Mpayhub-UAT/MpayHub
git pull
cd frontend && npm ci --legacy-peer-deps && npm run build && pm2 restart mpayhub-frontend
cd ../backend && ./venv/bin/pip install -r requirements-prod.txt   # when deps change
pm2 restart mpayhub-backend --update-env
nginx -t && systemctl reload nginx
```

**Deprecated (do not use):** `ecosystem.uat.config.cjs`, `scripts/uat-proxy.js`, `backend/run_gunicorn_uat.sh`.

---

## Production (partner.mpayhub.in)

Same PM2 ecosystem and ports (**8002** / **3002**) as UAT in this codebase. Older docs that mention API `:8000` or UI `:3001` as app binds are obsolete for this tree.

```bash
# Example on a dedicated prod host path — adjust to your checkout
~/MpayHub/scripts/setup-pm2-and-domain.sh
```

Prefer running PM2 as the deploy user (not `sudo pm2`) unless your host standard says otherwise.

### Production update

```bash
cd ~/MpayHub   # or your prod checkout
git pull
cd frontend && npm ci --legacy-peer-deps && npm run build && pm2 restart mpayhub-frontend
pm2 restart mpayhub-backend --update-env
nginx -t && systemctl reload nginx
pm2 save
```

---

## Cloudflare

- **Error 521:** origin not reachable — check nginx listening and tunnel/DNS.
- SSL mode must match how TLS is terminated (Flexible vs Full when origin has certs).

UAT tunnel example: `partner-uat.mpayhub.in` → `http://localhost:3001` (nginx). Keep `cloudflared` healthy: `systemctl status cloudflared`.

---

## Media storage (local or private S3)

Same code path: browser requests **same-origin** `/media/…`. DB stores relative keys.

| Setting | UAT | Prod |
|---------|-----|------|
| `USE_S3` | after cutover | after cutover |
| `AWS_S3_MEDIA_PREFIX` | `uat` | `prod` |
| Bucket / region | shared or split IAM | shared or split IAM |

On backend start (`run_gunicorn.sh`), if `USE_S3=True`, the process runs `sync_local_media_to_s3` (skip same-size existing objects).

```bash
cd backend && ./venv/bin/python manage.py sync_local_media_to_s3
./venv/bin/python manage.py verify_media_storage --limit 20
```

Do not delete local `media/` until cutover is verified for several days.

---

## Nginx configs

See [`nginx/`](nginx/) for host vhosts (UAT and prod). After edits:

```bash
nginx -t && systemctl reload nginx
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| API 502 | `pm2 logs mpayhub-backend`; ensure Gunicorn on `8002` |
| Login HTML 400 | `DJANGO_ENV` must not be `testing` on live; check `ALLOWED_HOSTS` |
| SPA calls wrong API host | Rebuild with `REACT_APP_API_BASE_URL=/api` |
| `react-scripts: not found` | `cd frontend && npm ci --legacy-peer-deps` |
| Media 404 after S3 | nginx `/media/` must **proxy** to Gunicorn, not stale disk `alias` only |
| Empty PM2 after reboot | `pm2 resurrect` or re-run setup script + `pm2 save` |

---

## Related

- Backend env & commands: [../backend/README.md](../backend/README.md)
- Security: [../SECURITY.md](../SECURITY.md)
