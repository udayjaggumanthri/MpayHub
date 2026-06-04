#!/usr/bin/env bash
# PM2 (backend + frontend) + nginx + origin TLS for partner.mpayhub.in
# Does not modify .env files.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
USER_NAME="${SUDO_USER:-$(whoami)}"

log() { echo "==> $*"; }

log "Ownership + frontend deps"
sudo chown -R "${USER_NAME}:${USER_NAME}" "$ROOT/frontend" "$ROOT/backend"
rm -rf "$ROOT/frontend/node_modules/.cache"
(
  cd "$ROOT/frontend"
  npm ci --legacy-peer-deps
  npm run build
)

log "Stop systemd backend (PM2 owns :8000)"
sudo systemctl stop mpayhub.service 2>/dev/null || true
sudo systemctl disable mpayhub.service 2>/dev/null || true

log "PM2 — backend + frontend"
sudo pm2 delete all 2>/dev/null || true
pm2 delete all 2>/dev/null || true
pm2 start "$ROOT/ecosystem.config.cjs"
pm2 save

log "PM2 on boot"
sudo mkdir -p /etc/systemd/system/pm2-ubuntu.service.d
sudo cp "$ROOT/deploy/systemd/pm2-ubuntu.override.conf" /etc/systemd/system/pm2-ubuntu.service.d/override.conf
if [[ ! -f /etc/systemd/system/pm2-ubuntu.service ]]; then
  sudo env PATH="/usr/local/bin:/usr/bin:/bin" pm2 startup systemd -u "${USER_NAME}" --hp "/home/${USER_NAME}"
fi
sudo systemctl daemon-reload
sudo systemctl enable pm2-ubuntu
sudo systemctl restart pm2-ubuntu

log "Origin TLS cert (Cloudflare Full SSL)"
sudo mkdir -p /etc/nginx/ssl
if [[ ! -f /etc/nginx/ssl/partner.mpayhub.in.crt ]]; then
  sudo openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/partner.mpayhub.in.key \
    -out /etc/nginx/ssl/partner.mpayhub.in.crt \
    -subj "/CN=partner.mpayhub.in" \
    -addext "subjectAltName=DNS:partner.mpayhub.in"
fi

log "Nginx"
sudo cp "$ROOT/deploy/nginx/partner.mpayhub.in.conf" /etc/nginx/sites-available/partner.mpayhub.in
sudo ln -sf /etc/nginx/sites-available/partner.mpayhub.in /etc/nginx/sites-enabled/partner.mpayhub.in
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

sleep 3
log "Health"
pm2 list
curl -sf -o /dev/null -H "Host: partner.mpayhub.in" http://127.0.0.1:3001/ || { echo "PM2 frontend :3001 failed"; exit 1; }
code=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: partner.mpayhub.in" http://127.0.0.1:8000/api/wallets/)
[[ "$code" == "401" || "$code" == "200" || "$code" == "403" ]] || { echo "PM2 backend :8000 unexpected $code"; exit 1; }
curl -sf -o /dev/null -k -H "Host: partner.mpayhub.in" https://127.0.0.1/ || { echo "nginx :443 failed"; exit 1; }

echo ""
echo "OK — https://partner.mpayhub.in/"
echo "  pm2 list          # backend + frontend"
echo "  Cloudflare SSL    # Full (recommended with origin :443) or Flexible"
