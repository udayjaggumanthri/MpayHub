/** Shallow compare for report filter objects (string values only). */
export function filtersEqual(a, b) {
  if (a === b) return true;
  if (!a || !b) return false;
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length) return false;
  return keysA.every((key) => String(a[key] ?? '') === String(b[key] ?? ''));
}

/** Count non-empty applied filters for the collapsed badge. */
export function countActiveReportFilters(filters, options = {}) {
  const {
    statusKey = 'status',
    ignoreStatus = ['ALL', 'all', ''],
    railKey = 'collectionRail',
    ignoreRail = ['all', ''],
    serviceTypeKey = 'serviceType',
    ignoreServiceType = ['all', ''],
  } = options;

  let count = 0;
  Object.entries(filters || {}).forEach(([key, raw]) => {
    const val = String(raw ?? '').trim();
    if (!val) return;
    if (key === statusKey && ignoreStatus.includes(val)) return;
    if (key === railKey && ignoreRail.includes(val)) return;
    if (key === serviceTypeKey && ignoreServiceType.includes(val)) return;
    count += 1;
  });
  return count;
}
