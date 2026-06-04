#!/usr/bin/env bash
# Deploy partner.mpayhub.in (UI + API). Does not modify .env files.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DEPLOY_USER="${SUDO_USER:-$(whoami)}"

log() { echo "==> $*"; }

log "Fix repo ownership (avoids EACCES after accidental sudo npm)"
if [[ "$(id -u)" -eq 0 ]]; then
  chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "$ROOT/frontend" "$ROOT/backend" 2>/dev/null || true
else
  sudo chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "$ROOT/frontend" 2>/dev/null || true
fi
rm -rf "$ROOT/frontend/node_modules/.cache"

log "Backend — systemd gunicorn (unix:/run/mpayhub.sock). Do NOT use PM2 for API."
sudo systemctl enable mpayhub.socket mpayhub.service
sudo systemctl restart mpayhub.service
systemctl is-active --quiet mpayhub.service

log "Frontend — npm ci + production build"
(
  cd "$ROOT/frontend"
  export NODE_ENV=production
  if [[ -f package-lock.json ]]; then
    npm ci --legacy-peer-deps
  else
    npm install --legacy-peer-deps
  fi
  npm run build
)
test -f "$ROOT/frontend/build/index.html"

log "PM2 — frontend optional (nginx serves build/); remove duplicate backends"
pm2 delete mpayhub-backend 2>/dev/null || true
sudo pm2 delete all 2>/dev/null || true
sudo pm2 save --force 2>/dev/null || true
if pm2 describe mpayhub-frontend >/dev/null 2>&1; then
  pm2 restart mpayhub-frontend
else
  pm2 start "$ROOT/ecosystem.config.cjs"
fi
pm2 save

log "PM2 on boot (optional; nginx serves production UI)"
if [[ ! -f /etc/systemd/system/pm2-ubuntu.service ]]; then
  sudo env PATH="/usr/local/bin:/usr/bin:/bin" pm2 startup systemd -u "${DEPLOY_USER}" --hp "/home/${DEPLOY_USER}" || true
fi
sudo mkdir -p /etc/systemd/system/pm2-ubuntu.service.d
sudo cp "$ROOT/deploy/systemd/pm2-ubuntu.override.conf" /etc/systemd/system/pm2-ubuntu.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl enable pm2-ubuntu 2>/dev/null || true
sudo systemctl restart pm2-ubuntu 2>/dev/null || true

log "Nginx — partner.mpayhub.in"
sudo cp "$ROOT/deploy/nginx/partner.mpayhub.in.conf" /etc/nginx/sites-available/partner.mpayhub.in
sudo ln -sf /etc/nginx/sites-available/partner.mpayhub.in /etc/nginx/sites-enabled/partner.mpayhub.in
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

log "Health checks"
curl -sf -o /dev/null -H "Host: partner.mpayhub.in" http://127.0.0.1/ || { echo "UI check failed"; exit 1; }
code=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: partner.mpayhub.in" http://127.0.0.1/api/wallets/)
[[ "$code" == "401" || "$code" == "200" || "$code" == "403" ]] || { echo "API check unexpected: $code"; exit 1; }

echo ""
echo "Deploy OK."
echo "  Site:  https://partner.mpayhub.in/"
echo "  API:   systemd mpayhub (not PM2)"
echo "  UI:    nginx → frontend/build"
echo "  PM2:   pm2 list (frontend only, optional)"
echo "  Logs:  sudo journalctl -u mpayhub -f"
