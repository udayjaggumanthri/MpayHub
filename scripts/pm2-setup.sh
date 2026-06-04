#!/usr/bin/env bash
# Recovery: PM2 frontend + systemd backend. Does not touch .env files.
# Production UI is served by nginx (frontend/build) — see scripts/deploy-partner.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

sudo chown -R "${USER}:${USER}" "$ROOT/frontend" 2>/dev/null || true

echo "==> Backend: systemd only"
sudo systemctl enable mpayhub.socket mpayhub.service
sudo systemctl restart mpayhub.service

echo "==> Remove PM2 backend / root PM2 duplicates"
pm2 delete mpayhub-backend 2>/dev/null || true
sudo pm2 delete all 2>/dev/null || true

echo "==> PM2 frontend (optional)"
if [[ ! -f frontend/node_modules/react-scripts/package.json ]]; then
  (cd frontend && npm ci --legacy-peer-deps)
fi
if pm2 describe mpayhub-frontend >/dev/null 2>&1; then
  pm2 restart mpayhub-frontend
else
  pm2 start ecosystem.config.cjs
fi
pm2 save
sudo env PATH="$PATH:/usr/bin" pm2 startup systemd -u "${USER}" --hp "${HOME}" 2>/dev/null || true

echo ""
pm2 list
echo "API: sudo systemctl status mpayhub"
echo "Site: run ~/MpayHub/scripts/deploy-partner.sh for nginx + build"
