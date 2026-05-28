/**
 * @deprecated Import from accessControl.js — re-exports for backward compatibility.
 */
export {
  ACCESS_CODES,
  ACCESS_ERROR_MESSAGES,
  ACCESS_ERROR_TITLES,
  ADMIN_ACCESS_ACTIONS,
  userMayLogin,
  isPayInOnlySession,
  isUserRestricted,
  isPaymentsLocked,
  userMayPayIn,
  userMayPayOut,
  isFinancialAppPath,
  isPayInAllowedPath,
  shouldBlockPathForUser,
  messageForAccessCode,
  messageForAccessDetail,
  parseApiAccessError,
  getAccessRedirectMessage,
  accountAccessBadges,
  getAccessCapabilityRows,
  formatAdminAccessSuccessMessage,
} from './accessControl';
