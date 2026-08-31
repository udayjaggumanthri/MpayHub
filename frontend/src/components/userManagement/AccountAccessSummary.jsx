import React from 'react';
import { getAccessCapabilityRows } from '../../utils/accessControl';

/** Admin: what this user can do right now (derived from flags). */
const AccountAccessSummary = ({ user }) => {
  const rows = getAccessCapabilityRows(user);
  if (!rows.length) return null;

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50 px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">
        Effective access
      </p>
      <ul className="space-y-1.5">
        {rows.map((row) => (
          <li key={row.label} className="flex items-center justify-between text-sm">
            <span className="text-slate-700 dark:text-slate-300">{row.label}</span>
            <span
              className={`font-semibold ${row.allowed ? 'text-emerald-700 dark:text-emerald-300' : 'text-slate-400 dark:text-slate-500'}`}
            >
              {row.allowed ? 'Allowed' : 'Blocked'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default AccountAccessSummary;
