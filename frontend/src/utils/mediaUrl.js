/** Resolve media/API asset URLs for split frontend (:3002) + backend (:8002) deploys. */

function apiOrigin() {
  const raw = (process.env.REACT_APP_API_BASE_URL || '').trim();
  if (!raw || raw.startsWith('/')) {
    // Relative API base (same host via nginx) — keep same-origin paths.
    return '';
  }
  try {
    const parsed = new URL(raw, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
    return parsed.origin;
  } catch {
    return '';
  }
}

/**
 * Same-origin path for /media/ and /api/ assets when UI and API share a host;
 * when REACT_APP_API_BASE_URL is absolute (e.g. http://IP:8002/api), rewrite
 * /api and /media to that backend origin so images load from Gunicorn.
 */
export function normalizeAssetUrl(url) {
  if (!url || typeof url !== 'string') return '';
  const trimmed = url.trim();
  if (!trimmed) return '';

  const origin = apiOrigin();

  if (trimmed.startsWith('/') && !trimmed.startsWith('//')) {
    if ((trimmed.startsWith('/api/') || trimmed.startsWith('/media/')) && origin) {
      return `${origin}${trimmed}`;
    }
    return trimmed;
  }

  try {
    const parsed = new URL(trimmed, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
    if (typeof window !== 'undefined' && parsed.origin === window.location.origin) {
      const path = `${parsed.pathname}${parsed.search}`;
      if ((path.startsWith('/api/') || path.startsWith('/media/')) && origin) {
        return `${origin}${path}`;
      }
      return path;
    }
    if (parsed.pathname.startsWith('/media/') || parsed.pathname.startsWith('/api/')) {
      if (origin) {
        return `${origin}${parsed.pathname}${parsed.search}`;
      }
      return `${parsed.pathname}${parsed.search}`;
    }
    return trimmed;
  } catch {
    return trimmed;
  }
}

export function payinQrReceiptApiUrl(transactionId, { download = false } = {}) {
  const base = `/api/fund-management/pay-in/qr/receipt/${encodeURIComponent(transactionId)}/`;
  return download ? `${base}?download=1` : base;
}

export function assetUrlNeedsAuth(url) {
  const normalized = normalizeAssetUrl(url);
  try {
    const parsed = new URL(normalized, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
    return parsed.pathname.startsWith('/api/');
  } catch {
    return normalized.includes('/api/');
  }
}
