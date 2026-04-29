/**
 * PM2 example for MpayHub (adjust paths for your VPS user/home).
 *
 * Frontend: must run `npm ci` (or `npm install`) and `npm run build` inside ./frontend
 * so ./frontend/build/index.html exists before starting.
 *
 * Usage:
 *   pm2 start ecosystem.config.cjs
 *   pm2 restart ecosystem.config.cjs --update-env
 */
const path = require('path');

const root = __dirname;

module.exports = {
  apps: [
    {
      name: 'mpayhub-frontend',
      cwd: path.join(root, 'frontend'),
      script: 'npm',
      args: 'run start:prod',
      interpreter: 'none',
      env: {
        NODE_ENV: 'production',
      },
    },
  ],
};
