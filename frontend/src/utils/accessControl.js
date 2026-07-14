/**
 * Access-control catalog and helpers (mirrors backend apps.core.access_catalog).
 * Single source for admin UX copy and end-user error messages.
 */
import { isModuleEnabled } from './maintenanceMode';

export const ACCESS_CODES = {
  ROLE_FINANCIAL_BLOCKED: 'ROLE_FINANCIAL_BLOCKED',
  USER_DISABLED: 'USER_DISABLED',
  USER_RESTRICTED: 'USER_RESTRICTED',
  USER_PAYMENTS_LOCKED: 'USER_PAYMENTS_LOCKED',
};

export const ACCESS_ERROR_MESSAGES = {
  [ACCESS_CODES.ROLE_FINANCIAL_BLOCKED]:
    'Your role cannot perform wallet transactions. Use the team and commission reports instead.',
  [ACCESS_CODES.USER_DISABLED]:
    'Your account is disabled. Contact your administrator.',
  [ACCESS_CODES.USER_RESTRICTED]:
    'Your account is restricted to read-only access. This action is not available.',
  [ACCESS_CODES.USER_PAYMENTS_LOCKED]:
    'Payments are locked on your account. You may still use pay-in and reports where allowed.',
};

export const ACCESS_ERROR_TITLES = {
  [ACCESS_CODES.ROLE_FINANCIAL_BLOCKED]: 'Transactions not available',
  [ACCESS_CODES.USER_DISABLED]: 'Account disabled',
  [ACCESS_CODES.USER_RESTRICTED]: 'Read-only account',
  [ACCESS_CODES.USER_PAYMENTS_LOCKED]: 'Payments locked',
};

/** Admin confirm-dialog presets (loosely coupled — UI imports by action key). */
export const ADMIN_ACCESS_ACTIONS = {
  disable_account: {
    title: 'Disable account?',
    tone: 'danger',
    confirmLabel: 'Disable account',
    bullets: [
      'User is signed out and cannot use the platform normally.',
      'Reports and wallet movements stop unless you allow pay-in below.',
    ],
    showPayInOption: true,
  },
  enable_account: {
    title: 'Enable account?',
    tone: 'success',
    confirmLabel: 'Enable account',
    bullets: [
      'User can sign in and use the platform according to their role.',
      'Previous pay-in-only exception is cleared.',
    ],
  },
  restrict_on: {
    title: 'Restrict to read-only?',
    tone: 'warning',
    confirmLabel: 'Apply restriction',
    bullets: [
      'User can view reports and profile only.',
      'Pay-in, payout, BBPS, and transfers are blocked.',
    ],
  },
  restrict_off: {
    title: 'Remove read-only restriction?',
    tone: 'success',
    confirmLabel: 'Remove restriction',
    bullets: ['User regains pay-in and payments per other account flags.'],
  },
  payments_lock_on: {
    title: 'Lock payments?',
    tone: 'warning',
    confirmLabel: 'Lock payments',
    bullets: [
      'Blocks payout, BBPS bill pay, and wallet transfers.',
      'Pay-in (load money) stays available unless the account is restricted or disabled.',
    ],
  },
  payments_lock_off: {
    title: 'Unlock payments?',
    tone: 'success',
    confirmLabel: 'Unlock payments',
    bullets: ['User can use payout, BBPS, and transfers again if otherwise allowed.'],
  },
};

export function userMayLogin(user) {
  if (!user) return false;
  if (user.access?.may_login != null) return Boolean(user.access.may_login);
  if (user.is_active !== false) return true;
  return Boolean(user.pay_in_allowed_when_disabled);
}

export function isPayInOnlySession(user) {
  if (!user) return false;
  if (user.is_active !== false) return false;
  return Boolean(user.pay_in_allowed_when_disabled);
}

/** Pay-in-only UX when load-money is actually available (not merely flagged on account). */
export function shouldShowPayInOnlyNotice(user, maintenance = null) {
  if (!user || isUserRestricted(user)) return false;
  if (!isPayInOnlySession(user)) return false;
  return canUsePayInModule(user, maintenance);
}

/** Redirect target after access-block or MPIN for pay-in-only users. */
export function getPayInOnlyRedirectPath(user, maintenance = null) {
  return shouldShowPayInOnlyNotice(user, maintenance)
    ? '/fund-management/load-money'
    : '/dashboard';
}

export function isUserRestricted(user) {
  return Boolean(user?.is_restricted);
}

export function isPaymentsLocked(user) {
  return Boolean(user?.payments_locked);
}

export function userMayPayIn(user) {
  if (!user) return false;
  if (user.access && typeof user.access === 'object' && user.access.may_pay_in != null) {
    return Boolean(user.access.may_pay_in);
  }
  if (!userMayLogin(user) || isUserRestricted(user)) return false;
  if (user.is_active === false && !user.pay_in_allowed_when_disabled) return false;
  return true;
}

/** Platform + account: pay-in / load-money is usable. */
export function isPayInModuleOperational(maintenance = null) {
  if (!maintenance) return true;
  return isModuleEnabled(maintenance, 'pay_in');
}

export function canUsePayInModule(user, maintenance = null) {
  return userMayPayIn(user) && isPayInModuleOperational(maintenance);
}

export function userMayPayOut(user) {
  if (user?.access?.may_pay_out != null) return Boolean(user.access.may_pay_out);
  if (!user || user.is_active === false || isUserRestricted(user) || isPaymentsLocked(user)) {
    return false;
  }
  return true;
}

const FINANCIAL_PATH_PREFIXES = ['/fund-management', '/bill-payments', '/wallets'];
const PAY_IN_ALLOWED_PATHS = ['/fund-management/load-money'];

export function isFinancialAppPath(path) {
  const p = String(path || '');
  return FINANCIAL_PATH_PREFIXES.some((prefix) => p === prefix || p.startsWith(`${prefix}/`));
}

export function isPayInAllowedPath(path) {
  const p = String(path || '');
  return PAY_IN_ALLOWED_PATHS.some((allowed) => p === allowed || p.startsWith(`${allowed}/`));
}

export function shouldBlockPathForUser(user, path) {
  if (!user) return false;
  if (isUserRestricted(user) && isFinancialAppPath(path)) return true;
  if (shouldShowPayInOnlyNotice(user) && isFinancialAppPath(path) && !isPayInAllowedPath(path)) {
    return true;
  }
  if (isPaymentsLocked(user) && isFinancialAppPath(path) && !isPayInAllowedPath(path)) {
    return true;
  }
  return false;
}

export function messageForAccessCode(code) {
  if (!code) return null;
  return ACCESS_ERROR_MESSAGES[code] || null;
}

export function titleForAccessCode(code) {
  if (!code) return 'Access limited';
  return ACCESS_ERROR_TITLES[code] || 'Access limited';
}

export function messageForAccessDetail(detail) {
  if (!detail) return null;
  if (typeof detail === 'string') return detail;
  const code = detail.code || '';
  if (code && ACCESS_ERROR_MESSAGES[code]) return ACCESS_ERROR_MESSAGES[code];
  return detail.message || null;
}

/** Parse standardized API error payloads (403 access denials). */
export function parseApiAccessError(result) {
  if (!result || result.success) return null;
  const code =
    result.errorCode ||
    result.error?.code ||
    (Array.isArray(result.errors) &&
      result.errors[0] &&
      typeof result.errors[0] === 'object' &&
      result.errors[0].code) ||
    null;
  if (code && ACCESS_ERROR_MESSAGES[code]) {
    return {
      code,
      title: titleForAccessCode(code),
      message: messageForAccessError(result, code),
    };
  }
  const msg = result.message || '';
  const matched = Object.keys(ACCESS_ERROR_MESSAGES).find((c) =>
    msg.toLowerCase().includes(ACCESS_ERROR_MESSAGES[c].toLowerCase().slice(0, 24))
  );
  if (matched) {
    return { code: matched, title: titleForAccessCode(matched), message: ACCESS_ERROR_MESSAGES[matched] };
  }
  return null;
}

function messageForAccessError(result, code) {
  const fromErrors =
    Array.isArray(result.errors) &&
    result.errors[0] &&
    typeof result.errors[0] === 'object' &&
    result.errors[0].message;
  return fromErrors || result.message || ACCESS_ERROR_MESSAGES[code];
}

export function getAccessRedirectMessage(user, path, maintenance = null) {
  return getBlockedActionNotice(user, path, maintenance);
}

/** Neutral end-user copy when Pay-Out / BBPS / other blocked financial routes are attempted. */
export const ACCESS_BLOCKED_TECHNICAL_MESSAGE =
  'Technical Error: Something went wrong, please contact us if the problem persists.';

/** Contextual notice when user attempts a route or action they cannot use. */
export function getBlockedActionNotice(user, path, maintenance = null) {
  if (!user) return ACCESS_BLOCKED_TECHNICAL_MESSAGE;

  if (isUserRestricted(user) && isFinancialAppPath(path)) {
    return ACCESS_BLOCKED_TECHNICAL_MESSAGE;
  }
  if (
    shouldShowPayInOnlyNotice(user, maintenance) &&
    isFinancialAppPath(path) &&
    !isPayInAllowedPath(path)
  ) {
    return ACCESS_BLOCKED_TECHNICAL_MESSAGE;
  }
  if (isPaymentsLocked(user) && isFinancialAppPath(path) && !isPayInAllowedPath(path)) {
    return ACCESS_BLOCKED_TECHNICAL_MESSAGE;
  }
  if (shouldBlockPathForUser(user, path)) {
    return ACCESS_BLOCKED_TECHNICAL_MESSAGE;
  }
  return ACCESS_BLOCKED_TECHNICAL_MESSAGE;
}

/**
 * Page-level block notice (e.g. payout screen) — shown only when user navigates there.
 * End-user wording does not expose restriction/lock reasons.
 * @param {'pay_in' | 'pay_out'} mode
 */
export function getPageAccessBlockNotice(user, mode = 'pay_out', maintenance = null) {
  if (!user) return null;

  if (mode === 'pay_in') {
    if (isUserRestricted(user) || !canUsePayInModule(user, maintenance)) {
      return {
        title: 'Technical Error',
        message: 'Something went wrong, please contact us if the problem persists.',
      };
    }
    return null;
  }

  if (isUserRestricted(user) || isPaymentsLocked(user) || shouldShowPayInOnlyNotice(user, maintenance)) {
    return {
      title: 'Technical Error',
      message: 'Something went wrong, please contact us if the problem persists.',
    };
  }
  return null;
}

export function accountAccessBadges(user) {
  if (!user) return [];
  const badges = [];
  if (user.is_active === false) {
    if (user.pay_in_allowed_when_disabled && userMayPayIn(user)) {
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

/** Compact capability matrix for admin profile panel. */
export function getAccessCapabilityRows(user) {
  if (!user) return [];
  return [
    { label: 'Sign in', allowed: userMayLogin(user) },
    { label: 'Pay-in (load money)', allowed: userMayPayIn(user) },
    { label: 'Payout / BBPS / transfers', allowed: userMayPayOut(user) },
  ];
}

/** End-user banner chips — omit modules that are hidden or inaccessible. */
export function getEndUserAccessCapabilityRows(user) {
  return getAccessCapabilityRows(user).filter((row) => {
    if (row.label.startsWith('Pay-in') && !userMayPayIn(user)) return false;
    return true;
  });
}

/**
 * Global proactive banners removed — use getBlockedActionNotice on blocked actions only.
 * @returns {null}
 */
export function getUserAccessNoticeVariant() {
  return null;
}

export function formatAdminAccessSuccessMessage(apiMessage) {
  return apiMessage || 'Access settings saved.';
}
