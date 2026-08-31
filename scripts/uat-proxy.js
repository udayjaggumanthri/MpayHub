#!/usr/bin/env node
/**
 * @deprecated Removed — UAT uses nginx (partner-uat.mpayhub.in) like production.
 * See scripts/setup-uat-pm2-and-domain.sh and deploy/nginx/partner-uat.mpayhub.in.conf
 */
const http = require('http');
const httpProxy = require('http-proxy');
const path = require('path');

const LISTEN_HOST = process.env.UAT_PROXY_HOST || '0.0.0.0';
const LISTEN_PORT = Number(process.env.UAT_PROXY_PORT || 3001);
const FRONTEND = process.env.UAT_FRONTEND_URL || 'http://127.0.0.1:3002';
const BACKEND = process.env.UAT_BACKEND_URL || 'http://127.0.0.1:8001';

const proxy = httpProxy.createProxyServer({
  xfwd: true,
  changeOrigin: false,
});

proxy.on('error', (err, _req, res) => {
  console.error('[uat-proxy]', err.message);
  if (res && !res.headersSent) {
    res.writeHead(502, { 'Content-Type': 'text/plain' });
    res.end('Bad gateway');
  }
});

function shouldProxyToBackend(urlPath) {
  return (
    urlPath.startsWith('/api/') ||
    urlPath.startsWith('/admin/') ||
    urlPath.startsWith('/backstatic/') ||
    urlPath.startsWith('/media/') ||
    urlPath === '/api' ||
    urlPath === '/admin'
  );
}

const server = http.createServer((req, res) => {
  const urlPath = (req.url || '/').split('?')[0];
  const target = shouldProxyToBackend(urlPath) ? BACKEND : FRONTEND;
  proxy.web(req, res, { target });
});

server.listen(LISTEN_PORT, LISTEN_HOST, () => {
  console.log(
    `[uat-proxy] listening on http://${LISTEN_HOST}:${LISTEN_PORT}` +
      ` | / → ${FRONTEND} | /api → ${BACKEND}`
  );
});
