# MpayHub production (partner.mpayhub.in)

## Architecture

| Component | PM2 app | Port |
|-----------|---------|------|
| **API** | `mpayhub-backend` | `127.0.0.1:8000` |
| **UI** | `mpayhub-frontend` | `3001` |
| **Domain** | nginx | `:80` + `:443` → proxies to PM2 |

```bash
~/MpayHub/scripts/setup-pm2-and-domain.sh   # full setup (PM2 + nginx + TLS)
```

**Never** run `sudo pm2` — use user `ubuntu` only.

## Deploy / update

```bash
cd ~/MpayHub
pm2 start ecosystem.config.cjs   # both apps
pm2 save
# after UI changes:
cd frontend && npm ci --legacy-peer-deps && npm run build && pm2 restart mpayhub-frontend
```

## Manual commands

```bash
# Backend
sudo systemctl restart mpayhub
sudo systemctl status mpayhub

# Frontend rebuild (if deploy script fails)
cd ~/MpayHub/frontend
npm ci --legacy-peer-deps
npm run build
sudo systemctl reload nginx

# PM2 (optional)
cd ~/MpayHub
pm2 list
pm2 logs mpayhub-frontend
```

## Cloudflare

If you see **Error 521**, set SSL/TLS mode to **Flexible** (origin listens on HTTP :80 only), or add an origin certificate and nginx `listen 443 ssl`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `react-scripts: not found` | `cd frontend && npm ci --legacy-peer-deps` |
| `EACCES` on npm | `sudo chown -R ubuntu:ubuntu ~/MpayHub/frontend` |
| `pm2 list` empty after reboot | `pm2 resurrect` or run deploy script |
| API 502 | `sudo systemctl restart mpayhub` |
| Wrong UI | Rebuild + `sudo systemctl reload nginx` |

---

## UAT (partner-uat.mpayhub.in)

Same architecture as production; repo path is `/root/Mpayhub-UAT/MpayHub`, PM2 runs as **root**.

| Component | PM2 app | Port |
|-----------|---------|------|
| **API** | `mpayhub-backend` | `127.0.0.1:8000` |
| **UI** | `mpayhub-frontend` | `127.0.0.1:3002` (internal) |
| **Domain** | nginx | `:80` + `:443` + **`:3001`** (Cloudflare Tunnel) → proxies to PM2 |

```bash
/root/Mpayhub-UAT/MpayHub/scripts/setup-uat-pm2-and-domain.sh   # full UAT setup
```

**Cloudflare Tunnel:** `partner-uat.mpayhub.in` → `http://localhost:3001` (nginx). Keep `cloudflared` running (`systemctl status cloudflared`).

### UAT deploy / update

```bash
cd /root/Mpayhub-UAT/MpayHub
pm2 restart mpayhub-backend                    # backend code
cd frontend && npm run build && pm2 restart mpayhub-frontend   # UI
nginx -t && systemctl reload nginx             # nginx config
```

**Deprecated (do not use):** `ecosystem.uat.config.cjs`, `scripts/uat-proxy.js`, `backend/run_gunicorn_uat.sh`.
