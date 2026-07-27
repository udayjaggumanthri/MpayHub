/**
 * Map DRF auth user payload (typically snake_case) to fields the UI expects.
 *
 * Identity layers (Safe Public User ID Redesign):
 *   display_code  — role-facing code (prefix updates on role change)
 *   member_id     — permanent MPH###### identity
 *   user_id / legacy_user_id — preserved legacy string
 */
export function resolveDisplayCode(raw) {
  if (!raw || typeof raw !== 'object') return '';
  return (
    raw.display_code ||
    raw.displayCode ||
    raw.user_id ||
    raw.userId ||
    raw.member_id ||
    raw.memberId ||
    raw.legacy_user_id ||
    raw.legacyUserId ||
    ''
  );
}

export function resolveMemberId(raw) {
  if (!raw || typeof raw !== 'object') return '';
  return raw.member_id || raw.memberId || '';
}

export function resolveLegacyUserId(raw) {
  if (!raw || typeof raw !== 'object') return '';
  return raw.legacy_user_id || raw.legacyUserId || raw.user_id || raw.userId || '';
}

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

  const displayCode = resolveDisplayCode(raw);
  const memberId = resolveMemberId(raw);
  const legacyUserId = resolveLegacyUserId(raw);
  // userId remains the primary UI label (display_code preferred).
  const userId = displayCode;

  return {
    ...raw,
    name,
    userId,
    displayCode,
    memberId,
    legacyUserId,
    display_code: displayCode || raw.display_code || '',
    member_id: memberId || raw.member_id || '',
    legacy_user_id: legacyUserId || raw.legacy_user_id || '',
    onboarding: raw.onboarding ?? null,
    is_active: raw.is_active !== false,
    is_restricted: Boolean(raw.is_restricted),
    payments_locked: Boolean(raw.payments_locked),
    pay_in_allowed_when_disabled: Boolean(raw.pay_in_allowed_when_disabled),
    access: raw.access && typeof raw.access === 'object' ? raw.access : null,
    profile: raw.profile && typeof raw.profile === 'object' ? raw.profile : null,
    kyc_verification:
      raw.kyc_verification && typeof raw.kyc_verification === 'object'
        ? raw.kyc_verification
        : null,
    profile_sync_pending: Array.isArray(raw.profile_sync_pending) ? raw.profile_sync_pending : [],
  };
}
