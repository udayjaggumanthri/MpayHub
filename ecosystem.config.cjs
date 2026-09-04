/**
 * PM2 — MpayHub production (localhost-only apps; nginx terminates TLS).
 *
 *   Domain / IP → nginx :80/:443
 *     /        → 127.0.0.1:3002  (frontend)
 *     /api/    → 127.0.0.1:8002  (backend)
 *     /media/  → backend/media/
 *
 * Frontend must be built with REACT_APP_API_BASE_URL=/api (same-origin).
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
        // Never use "testing" here — that settings module leaves ALLOWED_HOSTS empty
        // and login returns HTML 400 ("Gateway returned an HTML page instead of API JSON").
        DJANGO_ENV: 'development',
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
      args: ['-s', 'build', '-l', 'tcp://127.0.0.1:3002'],
      env: {
        NODE_ENV: 'production',
      },
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
    },
  ],
};
