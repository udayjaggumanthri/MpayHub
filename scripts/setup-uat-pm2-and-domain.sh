#!/usr/bin/env bash
# UAT: PM2 (backend + frontend) + nginx + origin TLS for partner-uat.mpayhub.in
# Does not modify .env files. Keeps other PM2 apps (e.g. mpayhub-marketing).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DOMAIN="partner-uat.mpayhub.in"
USER_NAME="${SUDO_USER:-$(whoami)}"

log() { echo "==> $*"; }

log "Ownership + frontend build"
chown -R "${USER_NAME}:${USER_NAME}" "$ROOT/frontend" "$ROOT/backend" 2>/dev/null || true
rm -rf "$ROOT/frontend/node_modules/.cache"
(
  cd "$ROOT/frontend"
  npm ci --legacy-peer-deps
  npm run build
)

log "Stop systemd backend if present (PM2 owns :8000)"
systemctl stop mpayhub.service 2>/dev/null || true
systemctl disable mpayhub.service 2>/dev/null || true

log "Remove legacy UAT PM2 apps (keep mpayhub-marketing and prod-named apps)"
pm2 delete mpayhub-uat-backend 2>/dev/null || true
pm2 delete mpayhub-uat-frontend 2>/dev/null || true
pm2 delete mpayhub-uat-proxy 2>/dev/null || true

log "PM2 — backend + frontend (production pattern)"
if pm2 describe mpayhub-backend >/dev/null 2>&1; then
  pm2 restart mpayhub-backend
else
  pm2 start "$ROOT/ecosystem.config.cjs" --only mpayhub-backend
fi
if pm2 describe mpayhub-frontend >/dev/null 2>&1; then
  pm2 restart mpayhub-frontend
else
  pm2 start "$ROOT/ecosystem.config.cjs" --only mpayhub-frontend
fi
pm2 save

log "PM2 on boot (root)"
env PATH="/usr/local/bin:/usr/bin:/bin" pm2 startup systemd -u "${USER_NAME}" --hp "${HOME}" 2>/dev/null || true
systemctl enable pm2-root 2>/dev/null || true
systemctl restart pm2-root 2>/dev/null || true

log "Origin TLS cert (Cloudflare Full SSL)"
mkdir -p /etc/nginx/ssl
if [[ ! -f /etc/nginx/ssl/partner-uat.mpayhub.in.crt ]]; then
  openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/partner-uat.mpayhub.in.key \
    -out /etc/nginx/ssl/partner-uat.mpayhub.in.crt \
    -subj "/CN=${DOMAIN}" \
    -addext "subjectAltName=DNS:${DOMAIN}"
fi

log "Nginx"
if ! command -v nginx >/dev/null 2>&1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx
fi
cp "$ROOT/deploy/nginx/partner-uat.mpayhub.in.conf" /etc/nginx/sites-available/partner-uat.mpayhub.in
ln -sf /etc/nginx/sites-available/partner-uat.mpayhub.in /etc/nginx/sites-enabled/partner-uat.mpayhub.in
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

log "Cloudflare Tunnel (partner-uat.mpayhub.in → nginx :3001)"
systemctl enable cloudflared 2>/dev/null || true
systemctl restart cloudflared 2>/dev/null || true

sleep 3
log "Health"
pm2 list
curl -sf -o /dev/null -H "Host: ${DOMAIN}" http://127.0.0.1:3001/ || { echo "nginx tunnel port :3001 failed"; exit 1; }
code=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: ${DOMAIN}" http://127.0.0.1:8000/api/wallets/)
[[ "$code" == "401" || "$code" == "200" || "$code" == "403" ]] || { echo "PM2 backend :8000 unexpected $code"; exit 1; }
curl -sf -o /dev/null -H "Host: ${DOMAIN}" http://127.0.0.1/ || { echo "nginx :80 failed"; exit 1; }
curl -sf -o /dev/null -k -H "Host: ${DOMAIN}" https://127.0.0.1/ || { echo "nginx :443 failed"; exit 1; }

echo ""
echo "OK — https://${DOMAIN}/"
echo "  pm2 list"
echo "  Cloudflare: A record → $(curl -s ifconfig.me 2>/dev/null || echo 'this VPS IP'), SSL mode Full"
