import React from 'react';
import { accountAccessBadges } from '../../utils/userAccess';

const toneClass = {
  emerald: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 ring-emerald-200/80 dark:ring-emerald-800/80',
  slate: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 ring-slate-200/80 dark:ring-slate-700/80',
  amber: 'bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-300 ring-amber-200/80 dark:ring-amber-800/80',
  violet: 'bg-violet-50 dark:bg-violet-950/40 text-violet-900 dark:text-violet-300 ring-violet-200/80 dark:ring-violet-800/80',
};

const AccessStatusBadges = ({ user, className = '' }) => {
  const badges = accountAccessBadges(user);
  if (!badges.length) return null;
  return (
    <div className={`flex flex-wrap gap-1.5 ${className}`}>
      {badges.map((b) => (
        <span
          key={b.key}
          className={`inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold ring-1 ${toneClass[b.tone] || toneClass.slate}`}
        >
          {b.label}
        </span>
      ))}
    </div>
  );
};

export default AccessStatusBadges;
