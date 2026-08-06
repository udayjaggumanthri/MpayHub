import React from 'react';

const TONES = {
  default: { value: 'text-slate-900', chip: 'bg-slate-100 text-slate-600' },
  success: { value: 'text-emerald-700', chip: 'bg-emerald-50 text-emerald-700' },
  warning: { value: 'text-amber-700', chip: 'bg-amber-50 text-amber-800' },
  danger: { value: 'text-red-600', chip: 'bg-red-50 text-red-700' },
  info: { value: 'text-blue-700', chip: 'bg-blue-50 text-blue-700' },
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
      className={`rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm ${
        onClick ? 'transition hover:border-blue-300 hover:shadow-md' : ''
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">
          {Icon && <Icon className="text-slate-400" size={14} />}
          {label}
        </span>
        {chip && <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${t.chip}`}>{chip}</span>}
      </div>
      <div className={`mt-2 text-2xl font-bold tracking-tight ${t.value}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </Wrapper>
  );
};

export default StatCard;
