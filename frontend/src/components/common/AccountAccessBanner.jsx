import React from 'react';
import { getPageAccessBlockNotice } from '../../utils/accessControl';

/**
 * Page-level alert when user opens a financial screen they cannot use.
 * @param {'pay_in' | 'pay_out'} mode
 */
const AccountAccessBanner = ({ user, mode = 'pay_out', maintenance = null }) => {
  const notice = getPageAccessBlockNotice(user, mode, maintenance);
  if (!notice) return null;

  return (
    <div
      className="mb-4 rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-4 py-3 text-sm text-amber-950 dark:text-amber-200"
      role="alert"
    >
      <p className="font-semibold">{notice.title}</p>
      <p className="mt-0.5 text-[13px] opacity-90">{notice.message}</p>
    </div>
  );
};

export default AccountAccessBanner;
