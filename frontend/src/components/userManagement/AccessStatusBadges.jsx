import React from 'react';
import { accountAccessBadges } from '../../utils/userAccess';

const toneClass = {
  emerald: 'bg-emerald-50 text-emerald-800 ring-emerald-200/80',
  slate: 'bg-slate-100 text-slate-700 ring-slate-200/80',
  amber: 'bg-amber-50 text-amber-900 ring-amber-200/80',
  violet: 'bg-violet-50 text-violet-900 ring-violet-200/80',
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
