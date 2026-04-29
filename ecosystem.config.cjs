/**
 * PM2 — MpayHub frontend (production static).
 *
 * Prerequisite (once per deploy, from repo root):
 *   cd frontend && npm ci && npm run build
 *
 * If you still see ENOENT for build/index.html or path-to-regexp errors, your old PM2
 * process is probably running a custom Express script. Remove it and start from this file:
 *   pm2 delete mpayhub-frontend
 *   pm2 start ecosystem.config.cjs --only mpayhub-frontend
 *
 * Do not use `pm2 restart` alone to change script/cwd — recreate the process.
 */
const path = require('path');

const root = __dirname;
const serveMain = path.join(root, 'frontend', 'node_modules', 'serve', 'build', 'main.js');

module.exports = {
  apps: [
    {
      name: 'mpayhub-frontend',
      cwd: path.join(root, 'frontend'),
      script: serveMain,
      interpreter: 'node',
      args: ['-s', 'build', '-l', '3001'],
      env: {
        NODE_ENV: 'production',
      },
    },
  ],
};
