/**
 * PM2 — MpayHub production (backend + frontend).
 *
 *   cd ~/MpayHub
 *   pm2 start ecosystem.config.cjs
 *   pm2 save
 *
 * Nginx (partner.mpayhub.in) proxies:
 *   /      → localhost:3001 (frontend)
 *   /api/  → localhost:8000 (backend)
 *
 * If you use systemd mpayhub instead, stop PM2 backend:
 *   pm2 delete mpayhub-backend && sudo systemctl start mpayhub
 */
const path = require('path');

const root = __dirname;
const serveMain = path.join(root, 'frontend', 'node_modules', 'serve', 'build', 'main.js');
const gunicornScript = path.join(root, 'backend', 'run_gunicorn.sh');

module.exports = {
  apps: [
    {
      name: 'mpayhub-backend',
      cwd: path.join(root, 'backend'),
      script: gunicornScript,
      interpreter: 'bash',
      env: {
        DJANGO_SETTINGS_MODULE: 'config.settings',
      },
      autorestart: true,
      max_restarts: 15,
      min_uptime: '10s',
      restart_delay: 3000,
    },
    {
      name: 'mpayhub-frontend',
      cwd: path.join(root, 'frontend'),
      script: serveMain,
      interpreter: 'node',
      args: ['-s', 'build', '-l', '3001'],
      env: {
        NODE_ENV: 'production',
      },
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
    },
  ],
};
