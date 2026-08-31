/** Same-origin path for /media/ and /api/ assets (fixes http/https host mismatches behind proxy). */
export function normalizeAssetUrl(url) {
  if (!url || typeof url !== 'string') return '';
  const trimmed = url.trim();
  if (!trimmed) return '';
  if (trimmed.startsWith('/') && !trimmed.startsWith('//')) return trimmed;
  try {
    const parsed = new URL(trimmed, window.location.origin);
    if (parsed.origin === window.location.origin) {
      return `${parsed.pathname}${parsed.search}`;
    }
    if (parsed.pathname.startsWith('/media/') || parsed.pathname.startsWith('/api/')) {
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
  return normalized.startsWith('/api/');
}
