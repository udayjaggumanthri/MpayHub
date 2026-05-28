import React from 'react';
import {
  ACCESS_ERROR_MESSAGES,
  isPayInOnlySession,
  isPaymentsLocked,
  isUserRestricted,
  titleForAccessCode,
  ACCESS_CODES,
} from '../../utils/accessControl';

/**
 * @param {'pay_in' | 'pay_out'} mode
 */
const AccountAccessBanner = ({ user, mode = 'pay_out' }) => {
  if (!user) return null;

  let code = null;
  if (mode === 'pay_in' && isUserRestricted(user)) {
    code = ACCESS_CODES.USER_RESTRICTED;
  } else if (mode === 'pay_out') {
    if (isUserRestricted(user)) code = ACCESS_CODES.USER_RESTRICTED;
    else if (isPaymentsLocked(user)) code = ACCESS_CODES.USER_PAYMENTS_LOCKED;
    else if (isPayInOnlySession(user)) code = ACCESS_CODES.USER_DISABLED;
  }

  if (!code) return null;

  const title = titleForAccessCode(code);
  const message = ACCESS_ERROR_MESSAGES[code];

  return (
    <div
      className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
      role="alert"
    >
      <p className="font-semibold">{title}</p>
      <p className="mt-0.5 text-[13px] opacity-90">{message}</p>
    </div>
  );
};

export default AccountAccessBanner;
