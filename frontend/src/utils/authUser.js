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
    // Backend omits is_active only for very old payloads; treat as active.
    is_active: raw.is_active !== false,
  };
}
