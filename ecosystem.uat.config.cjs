/**
 * @deprecated Use ecosystem.config.cjs + scripts/setup-uat-pm2-and-domain.sh
 * Legacy UAT stack (uat-proxy on :3001, backend :8001, frontend :3002) — removed.
 */
const path = require('path');

const root = __dirname;
const serveMain = path.join(root, 'frontend', 'node_modules', 'serve', 'build', 'main.js');
const gunicornScript = path.join(root, 'backend', 'run_gunicorn_uat.sh');
const uatProxy = path.join(root, 'scripts', 'uat-proxy.js');

module.exports = {
  apps: [
    {
      name: 'mpayhub-uat-backend',
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
      name: 'mpayhub-uat-frontend',
      cwd: path.join(root, 'frontend'),
      script: serveMain,
      interpreter: 'node',
      args: ['-s', 'build', '-l', 'tcp://127.0.0.1:3002'],
      env: {
        NODE_ENV: 'production',
      },
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
    },
    {
      name: 'mpayhub-uat-proxy',
      cwd: root,
      script: uatProxy,
      interpreter: 'node',
      env: {
        UAT_PROXY_PORT: '3001',
        UAT_FRONTEND_URL: 'http://127.0.0.1:3002',
        UAT_BACKEND_URL: 'http://127.0.0.1:8001',
      },
      autorestart: true,
      max_restarts: 15,
      min_uptime: '5s',
    },
  ],
};
