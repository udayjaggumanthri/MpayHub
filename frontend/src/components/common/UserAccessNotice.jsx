import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { FaCircleInfo, FaLock, FaUserSlash } from 'react-icons/fa6';
import { useAuth } from '../../context/AuthContext';
import {
  getAccessCapabilityRows,
  isPayInOnlySession,
  isPaymentsLocked,
  isUserRestricted,
  userMayLogin,
} from '../../utils/accessControl';

/**
 * Global banner for the signed-in user's access state (enterprise ops visibility).
 */
const UserAccessNotice = () => {
  const { user } = useAuth();
  const location = useLocation();

  if (!user || !userMayLogin(user)) return null;

  const payInOnly = isPayInOnlySession(user);
  const restricted = isUserRestricted(user);
  const paymentsLocked = isPaymentsLocked(user);

  if (!payInOnly && !restricted && !paymentsLocked) return null;

  let title = '';
  let body = '';
  let tone = 'amber';
  let Icon = FaCircleInfo;

  if (restricted) {
    title = 'Read-only account';
    body = 'You can use reports and profile. Pay-in and payments are not available.';
    tone = 'violet';
    Icon = FaLock;
  } else if (payInOnly) {
    title = 'Pay-in only mode';
    body = 'Your account is disabled for full access. You may sign in only to load money.';
    Icon = FaUserSlash;
  } else if (paymentsLocked) {
    title = 'Payments locked';
    body = 'Payout, BBPS, and transfers are paused. Pay-in and reports may still be available.';
    Icon = FaLock;
  }

  const toneClass =
    tone === 'violet'
      ? 'border-violet-200 bg-violet-50 text-violet-950'
      : 'border-amber-200 bg-amber-50 text-amber-950';

  const caps = getAccessCapabilityRows(user);
  const onLoadMoney = location.pathname.startsWith('/fund-management/load-money');

  return (
    <div className={`mb-4 rounded-xl border px-4 py-3 text-sm ${toneClass}`} role="status">
      <div className="flex flex-wrap items-start gap-3">
        <Icon className="mt-0.5 shrink-0 opacity-80" size={18} aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{title}</p>
          <p className="mt-0.5 text-[13px] opacity-90">{body}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {caps.map((row) => (
              <span
                key={row.label}
                className={`inline-flex rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ${
                  row.allowed
                    ? 'bg-white/80 text-emerald-800 ring-emerald-200/80'
                    : 'bg-white/50 text-slate-500 ring-slate-200/80 line-through'
                }`}
              >
                {row.label}
              </span>
            ))}
          </div>
          {payInOnly && !onLoadMoney ? (
            <Link
              to="/fund-management/load-money"
              className="mt-2 inline-block text-[13px] font-semibold underline underline-offset-2"
            >
              Go to Load Money →
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default UserAccessNotice;
