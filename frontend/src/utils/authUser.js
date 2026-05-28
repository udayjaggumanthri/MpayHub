/**
 * Map DRF auth user payload (typically snake_case) to fields the UI expects.
 */
export function normalizeAuthUser(raw) {
  if (!raw || typeof raw !== 'object') return null;

  const first = raw.first_name ?? raw.firstName ?? '';
  const last = raw.last_name ?? raw.lastName ?? '';
  const fullName = [first, last].filter(Boolean).join(' ').trim();

  const name =
    fullName ||
    (typeof raw.name === 'string' ? raw.name.trim() : '') ||
    raw.email ||
    raw.phone ||
    'User';

  const userId = raw.user_id ?? raw.userId ?? '';

  return {
    ...raw,
    name,
    userId,
    onboarding: raw.onboarding ?? null,
    is_active: raw.is_active !== false,
    is_restricted: Boolean(raw.is_restricted),
    payments_locked: Boolean(raw.payments_locked),
    pay_in_allowed_when_disabled: Boolean(raw.pay_in_allowed_when_disabled),
    access: raw.access && typeof raw.access === 'object' ? raw.access : null,
  };
}
