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
