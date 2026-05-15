/**
 * Per-user access helpers (mirror backend apps.core.financial_access).
 */

export const ACCESS_ERROR_MESSAGES = {
  ROLE_FINANCIAL_BLOCKED:
    'Your role cannot perform wallet transactions. Use the team and commission reports instead.',
  USER_DISABLED: 'Your account is disabled. Contact your administrator.',
  USER_RESTRICTED:
    'Your account is restricted to read-only access. This action is not available.',
  USER_PAYMENTS_LOCKED:
    'Payments are locked on your account. You may still use pay-in and reports where allowed.',
};

export function userMayLogin(user) {
  if (!user) return false;
  if (user.is_active !== false) return true;
  return Boolean(user.pay_in_allowed_when_disabled);
}

/** Disabled account that may only log in for pay-in (load money). */
export function isPayInOnlySession(user) {
  if (!user) return false;
  return user.is_active === false && Boolean(user.pay_in_allowed_when_disabled);
}

export function isUserRestricted(user) {
  return Boolean(user?.is_restricted);
}

export function isPaymentsLocked(user) {
  return Boolean(user?.payments_locked);
}

const FINANCIAL_PATH_PREFIXES = [
  '/fund-management',
  '/bill-payments',
  '/wallets',
];

const PAY_IN_ALLOWED_PATHS = ['/fund-management/load-money'];

export function isFinancialAppPath(path) {
  const p = String(path || '');
  return FINANCIAL_PATH_PREFIXES.some((prefix) => p === prefix || p.startsWith(`${prefix}/`));
}

export function isPayInAllowedPath(path) {
  const p = String(path || '');
  return PAY_IN_ALLOWED_PATHS.some((allowed) => p === allowed || p.startsWith(`${allowed}/`));
}

/** Whether this route should be blocked for the current user's access flags. */
export function shouldBlockPathForUser(user, path) {
  if (!user) return false;
  if (isUserRestricted(user) && isFinancialAppPath(path)) {
    return true;
  }
  if (isPayInOnlySession(user) && isFinancialAppPath(path) && !isPayInAllowedPath(path)) {
    return true;
  }
  if (isPaymentsLocked(user) && isFinancialAppPath(path) && !isPayInAllowedPath(path)) {
    return true;
  }
  return false;
}

export function messageForAccessDetail(detail) {
  if (!detail) return null;
  if (typeof detail === 'string') return detail;
  const code = detail.code || '';
  if (code && ACCESS_ERROR_MESSAGES[code]) {
    return ACCESS_ERROR_MESSAGES[code];
  }
  return detail.message || null;
}

/** Admin list/detail badge labels (priority order). */
export function accountAccessBadges(user) {
  if (!user) return [];
  const badges = [];
  if (user.is_active === false) {
    if (user.pay_in_allowed_when_disabled) {
      badges.push({ key: 'payin_only', label: 'Pay-in only', tone: 'amber' });
    } else {
      badges.push({ key: 'disabled', label: 'Disabled', tone: 'slate' });
    }
  } else {
    badges.push({ key: 'active', label: 'Active', tone: 'emerald' });
  }
  if (user.is_restricted) {
    badges.push({ key: 'restricted', label: 'Restricted', tone: 'violet' });
  }
  if (user.payments_locked) {
    badges.push({ key: 'payments_locked', label: 'Payments locked', tone: 'amber' });
  }
  return badges;
}
