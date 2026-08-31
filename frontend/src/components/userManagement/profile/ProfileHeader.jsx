import React from 'react';
import { FaArrowLeft } from 'react-icons/fa6';
import AccessStatusBadges from '../AccessStatusBadges';

const roleBadgeClass = (role) => {
  const map = {
    Admin: 'bg-violet-100 dark:bg-violet-900/40 text-violet-900 dark:text-violet-300 ring-1 ring-violet-200 dark:ring-violet-800',
    'Super Distributor': 'bg-sky-100 dark:bg-sky-900/40 text-sky-900 dark:text-sky-300 ring-1 ring-sky-200 dark:ring-sky-800',
    'Master Distributor': 'bg-cyan-100 dark:bg-cyan-900/40 text-cyan-900 dark:text-cyan-300 ring-1 ring-cyan-200 dark:ring-cyan-800',
    Distributor: 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-900 dark:text-indigo-300 ring-1 ring-indigo-200 dark:ring-indigo-800',
    Retailer: 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 ring-1 ring-slate-200 dark:ring-slate-700',
  };
  return map[role || ''] || 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 ring-1 ring-slate-200 dark:ring-slate-700';
};

/**
 * Compact enterprise profile header (back, name, role, status).
 */
const ProfileHeader = ({ fullName, user, onBack }) => (
  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
    <div className="flex items-center gap-4">
      <button
        type="button"
        onClick={onBack}
        className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 shadow-sm transition-colors hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100"
        aria-label="Go back"
      >
        <FaArrowLeft size={16} />
      </button>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">User profile</p>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">{fullName}</h1>
        <p className="mt-0.5 font-mono text-sm text-slate-500 dark:text-slate-400">
          {[user?.display_code || user?.user_id, user?.member_id].filter(Boolean).join(' · ')}
        </p>
      </div>
    </div>
    <div className="flex flex-wrap items-center gap-2 sm:justify-end">
      <span
        className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-semibold ${roleBadgeClass(
          user?.role
        )}`}
      >
        {user?.role}
      </span>
      <AccessStatusBadges user={user} className="justify-end" />
    </div>
  </div>
);

export default ProfileHeader;
