export const BBPS_CANONICAL_CATEGORIES = [
  { displayName: 'Agent Collection', primarySlug: 'agent-collection', slugAliases: ['agentcollection'] },
  { displayName: 'Broadband Postpaid', primarySlug: 'broadband-postpaid', slugAliases: ['broadband', 'broad-band'] },
  { displayName: 'Cable TV', primarySlug: 'cable-tv', slugAliases: ['cable', 'cabletv'] },
  { displayName: 'Clubs and Associations', primarySlug: 'clubs-and-associations', slugAliases: ['clubs-associations', 'clubs'] },
  { displayName: 'Credit Card', primarySlug: 'credit-card', slugAliases: ['creditcard', 'credit-card-bill', 'cc', 'credit card'] },
  { displayName: 'DTH', primarySlug: 'dth', slugAliases: ['direct-to-home'] },
  { displayName: 'eChallan', primarySlug: 'echallan', slugAliases: ['e-challan', 'challan'] },
  { displayName: 'Education Fees', primarySlug: 'education-fees', slugAliases: ['education', 'education fee'] },
  { displayName: 'Electricity', primarySlug: 'electricity', slugAliases: ['electric'] },
  { displayName: 'EV Recharge', primarySlug: 'ev-recharge', slugAliases: ['ev', 'electric-vehicle'] },
  { displayName: 'FASTag', primarySlug: 'fastag', slugAliases: ['fast-tag', 'fast tag', 'fastag recharge'] },
  { displayName: 'Fleet Card Recharge', primarySlug: 'fleet-card-recharge', slugAliases: ['fleet-card', 'fleet card'] },
  { displayName: 'Gas', primarySlug: 'gas', slugAliases: ['piped-gas', 'png'] },
  { displayName: 'Housing Society', primarySlug: 'housing-society', slugAliases: ['housing', 'housing society'] },
  { displayName: 'Insurance', primarySlug: 'insurance', slugAliases: ['life-insurance', 'general-insurance'] },
  { displayName: 'Landline Postpaid', primarySlug: 'landline-postpaid', slugAliases: ['landline', 'land line'] },
  { displayName: 'Loan Repayment', primarySlug: 'loan-repayment', slugAliases: ['loan-emi', 'loan', 'loan repayment'] },
  { displayName: 'LPG Gas', primarySlug: 'lpg-gas', slugAliases: ['lpg', 'lpg gas'] },
  { displayName: 'Mobile Postpaid', primarySlug: 'mobile-postpaid', slugAliases: ['mobile-recharge', 'mobile', 'mobile postpaid'] },
  { displayName: 'Mobile Prepaid', primarySlug: 'mobile-prepaid', slugAliases: ['mobile prepaid', 'prepaid-mobile'] },
  { displayName: 'Municipal Services', primarySlug: 'municipal-services', slugAliases: ['municipal', 'municipality'] },
  { displayName: 'Municipal Taxes', primarySlug: 'municipal-taxes', slugAliases: ['municipal-tax', 'property-tax'] },
  { displayName: 'National Pension System', primarySlug: 'national-pension-system', slugAliases: ['nps', 'pension'] },
  { displayName: 'NCMC Recharge', primarySlug: 'ncmc-recharge', slugAliases: ['ncmc', 'ncmc recharge'] },
  { displayName: 'Prepaid Meter', primarySlug: 'prepaid-meter', slugAliases: ['prepaid', 'smart-meter'] },
  { displayName: 'Rental', primarySlug: 'rental', slugAliases: ['rent', 'rent payment'] },
  { displayName: 'Subscription', primarySlug: 'subscription', slugAliases: ['subscriptions'] },
  { displayName: 'Water', primarySlug: 'water', slugAliases: ['water bill'] },
];

export function normalizeCategorySlug(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[_\s]+/g, '-')
    .replace(/-+/g, '-');
}

export function categoryMatchesApiSlug(category, apiSlug) {
  const n = normalizeCategorySlug(apiSlug);
  if (!n) return false;
  const primary = normalizeCategorySlug(category.primarySlug);
  if (primary === n) return true;
  return (category.slugAliases || []).some((alias) => normalizeCategorySlug(alias) === n);
}

export function isCategoryAvailable(category, availableSlugSet) {
  if (!availableSlugSet || availableSlugSet.size === 0) return false;
  if (categoryMatchesApiSlug(category, category.primarySlug)) {
    if (availableSlugSet.has(normalizeCategorySlug(category.primarySlug))) return true;
  }
  return (category.slugAliases || []).some((alias) => availableSlugSet.has(normalizeCategorySlug(alias)))
    || [...availableSlugSet].some((slug) => categoryMatchesApiSlug(category, slug));
}

export function findCanonicalCategory(slug) {
  const n = normalizeCategorySlug(slug);
  if (!n) return null;
  return (
    BBPS_CANONICAL_CATEGORIES.find(
      (cat) => normalizeCategorySlug(cat.primarySlug) === n || categoryMatchesApiSlug(cat, n)
    ) || null
  );
}

/** Pick API route slug for biller fetch (prefers active backend category id). */
export function resolveCategoryRouteSlug(slug, availableSlugSet = new Set()) {
  const n = normalizeCategorySlug(slug);
  const canonical = findCanonicalCategory(n);
  const trySlug = (candidate) => {
    const c = normalizeCategorySlug(candidate);
    if (!c) return null;
    if (!availableSlugSet.size || availableSlugSet.has(c)) return c;
    return null;
  };

  if (canonical) {
    const primary = trySlug(canonical.primarySlug);
    if (primary) return primary;
    for (const alias of canonical.slugAliases || []) {
      const hit = trySlug(alias);
      if (hit) return hit;
    }
    for (const avail of availableSlugSet) {
      if (categoryMatchesApiSlug(canonical, avail)) return avail;
    }
    return canonical.primarySlug;
  }

  return trySlug(n) || n;
}

/**
 * Full catalog: canonical list + any extra categories returned by the API.
 */
export function buildCategoryCatalog(apiCategories = []) {
  const apiRows = (Array.isArray(apiCategories) ? apiCategories : [])
    .map((row) => ({
      id: normalizeCategorySlug(row.id || row.code),
      name: String(row.name || row.displayName || row.id || '').trim(),
    }))
    .filter((row) => row.id);

  const availableSlugSet = new Set(apiRows.map((r) => r.id));
  const apiNameBySlug = Object.fromEntries(apiRows.map((r) => [r.id, r.name]));

  const canonicalRows = BBPS_CANONICAL_CATEGORIES.map((category) => {
    const hasBillers = isCategoryAvailable(category, availableSlugSet);
    const matchedApiSlug =
      [...availableSlugSet].find((slug) => categoryMatchesApiSlug(category, slug)) || null;
    return {
      ...category,
      hasBillers,
      apiSlug: matchedApiSlug || category.primarySlug,
      displayName:
        (matchedApiSlug && apiNameBySlug[matchedApiSlug]) || category.displayName,
    };
  });

  const extras = apiRows
    .filter((api) => !BBPS_CANONICAL_CATEGORIES.some((cat) => categoryMatchesApiSlug(cat, api.id)))
    .map((api) => ({
      displayName: api.name || api.id.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      primarySlug: api.id,
      slugAliases: [],
      hasBillers: true,
      apiSlug: api.id,
      fromApi: true,
    }));

  return [...canonicalRows, ...extras];
}
