/**
 * Normalize contacts list API responses (paginated DRF or legacy `contacts` key).
 */
export function contactsFromListResult(result) {
  if (!result?.success || !result.data) {
    return { contacts: [], totalCount: null };
  }
  const d = result.data;
  if (Array.isArray(d.contacts)) {
    return {
      contacts: d.contacts,
      totalCount: typeof d.count === 'number' ? d.count : d.contacts.length,
    };
  }
  if (Array.isArray(d.results)) {
    return {
      contacts: d.results,
      totalCount: typeof d.count === 'number' ? d.count : d.results.length,
    };
  }
  if (Array.isArray(d)) {
    return { contacts: d, totalCount: d.length };
  }
  return { contacts: [], totalCount: null };
}

/** Map API contact row to a stable shape for fund flows. */
export function mapContactRow(row) {
  if (!row) return null;
  return {
    id: row.id,
    name: row.name || '',
    email: row.email ?? '',
    phone: row.phone || '',
  };
}
