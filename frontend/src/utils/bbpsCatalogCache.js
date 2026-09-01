const TTL_MS = 3 * 60 * 1000;
const BILLER_PREFIX = 'mpayhub:bbps:billers:v1:';
const CATEGORY_KEY = 'mpayhub:bbps:categories:v1';
const CATALOG_UX_KEY = 'mpayhub:bbps:catalog_ux:v1';

export function readCategoryListCache() {
  try {
    const raw = sessionStorage.getItem(CATEGORY_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || Date.now() - Number(parsed.ts || 0) > TTL_MS) return null;
    return Array.isArray(parsed.categories) ? parsed.categories : null;
  } catch {
    return null;
  }
}

export function writeCategoryListCache(categories) {
  if (!Array.isArray(categories)) return;
  try {
    sessionStorage.setItem(CATEGORY_KEY, JSON.stringify({ ts: Date.now(), categories }));
  } catch {
    /* quota / private mode */
  }
}

export function readBillerListCache(category) {
  try {
    const raw = sessionStorage.getItem(`${BILLER_PREFIX}${category}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || Date.now() - Number(parsed.ts || 0) > TTL_MS) return null;
    return Array.isArray(parsed.billers) ? parsed.billers : null;
  } catch {
    return null;
  }
}

export function writeBillerListCache(category, billers) {
  if (!category || !Array.isArray(billers)) return;
  try {
    sessionStorage.setItem(
      `${BILLER_PREFIX}${category}`,
      JSON.stringify({ ts: Date.now(), billers })
    );
  } catch {
    /* quota / private mode */
  }
}

/** Clear category + biller session caches when catalog UX mode changes (e.g. cash-only toggle). */
export function clearBbpsCatalogSessionCache() {
  try {
    const keys = [];
    for (let i = 0; i < sessionStorage.length; i += 1) {
      const key = sessionStorage.key(i);
      if (key && (key === CATEGORY_KEY || key.startsWith(BILLER_PREFIX))) {
        keys.push(key);
      }
    }
    keys.forEach((key) => sessionStorage.removeItem(key));
  } catch {
    /* private mode */
  }
}

/**
 * If server catalog_ux.cash_only_for_users changed, clear stale session caches.
 * Returns true when caches were cleared.
 */
export function syncCatalogUxMode(catalogUx) {
  const cashOnly = Boolean(catalogUx?.cash_only_for_users);
  try {
    const raw = sessionStorage.getItem(CATALOG_UX_KEY);
    const prev = raw ? JSON.parse(raw) : null;
    const prevCashOnly = prev ? Boolean(prev.cash_only_for_users) : null;
    sessionStorage.setItem(
      CATALOG_UX_KEY,
      JSON.stringify({ ts: Date.now(), cash_only_for_users: cashOnly })
    );
    if (prevCashOnly !== null && prevCashOnly !== cashOnly) {
      clearBbpsCatalogSessionCache();
      return true;
    }
  } catch {
    /* quota / private mode */
  }
  return false;
}

export function prefetchBillerList(category, fetchBillers) {
  const slug = String(category || '').trim();
  if (!slug || typeof fetchBillers !== 'function') return Promise.resolve(null);
  const cached = readBillerListCache(slug);
  if (cached) return Promise.resolve(cached);
  const existing = _billerPrefetchInflight.get(slug);
  if (existing) return existing;
  const pending = Promise.resolve(fetchBillers(slug))
    .then((res) => {
      const billers = res?.success && Array.isArray(res.data?.billers) ? res.data.billers : [];
      writeBillerListCache(slug, billers);
      return billers;
    })
    .catch(() => null)
    .finally(() => {
      _billerPrefetchInflight.delete(slug);
    });
  _billerPrefetchInflight.set(slug, pending);
  return pending;
}

const _billerPrefetchInflight = new Map();
