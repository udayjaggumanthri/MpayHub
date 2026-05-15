import React from 'react';
import {
  ACCESS_ERROR_MESSAGES,
  isPayInOnlySession,
  isPaymentsLocked,
  isUserRestricted,
} from '../../utils/userAccess';

/**
 * @param {'pay_in' | 'pay_out'} mode
 */
const AccountAccessBanner = ({ user, mode = 'pay_out' }) => {
  if (!user) return null;

  let message = null;
  if (mode === 'pay_in' && isUserRestricted(user)) {
    message = ACCESS_ERROR_MESSAGES.USER_RESTRICTED;
  } else if (mode === 'pay_out') {
    if (isUserRestricted(user)) {
      message = ACCESS_ERROR_MESSAGES.USER_RESTRICTED;
    } else if (isPaymentsLocked(user)) {
      message = ACCESS_ERROR_MESSAGES.USER_PAYMENTS_LOCKED;
    } else if (isPayInOnlySession(user)) {
      message =
        'Your account is limited to pay-in only. Payment outflows are not available until your administrator re-enables full access.';
    }
  }

  if (!message) return null;

  return (
    <div
      className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
      role="status"
    >
      {message}
    </div>
  );
};

export default AccountAccessBanner;
