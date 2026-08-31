import React from 'react';

const TONES = {
  default: { value: 'text-slate-900 dark:text-slate-100', chip: 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400' },
  success: { value: 'text-emerald-700 dark:text-emerald-300', chip: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300' },
  warning: { value: 'text-amber-700 dark:text-amber-300', chip: 'bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300' },
  danger: { value: 'text-red-600 dark:text-red-400', chip: 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300' },
  info: { value: 'text-blue-700 dark:text-blue-300', chip: 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300' },
};

/**
 * KPI stat card: label, big value, optional sub-line + tone + icon + chip text.
 */
const StatCard = ({ label, value, sub, tone = 'default', icon: Icon, chip, onClick }) => {
  const t = TONES[tone] || TONES.default;
  const Wrapper = onClick ? 'button' : 'div';
  return (
    <Wrapper
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={`rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 text-left shadow-sm ${
        onClick ? 'transition hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-md' : ''
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {Icon && <Icon className="text-slate-400 dark:text-slate-500" size={14} />}
          {label}
        </span>
        {chip && <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${t.chip}`}>{chip}</span>}
      </div>
      <div className={`mt-2 text-2xl font-bold tracking-tight ${t.value}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{sub}</div>}
    </Wrapper>
  );
};

export default StatCard;
