import React from 'react';
import {
  REPORT_PERIODS,
  REPORT_PERIOD_LABELS,
  REPORT_PERIOD_SUBTITLES,
} from '../../utils/reportPeriodRange';

/**
 * Compact Day / Week / Month / 2 months / Year control for report summary tiles.
 */
const ReportSummaryPeriodToggle = ({
  period = 'day',
  onChange,
  refreshing = false,
  className = '',
}) => {
  if (typeof onChange !== 'function') return null;

  return (
    <div
      className={`flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between ${className}`}
    >
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Summary for{' '}
        <span className="font-semibold text-slate-700 dark:text-slate-200">
          {REPORT_PERIOD_SUBTITLES[period] || 'Today'}
        </span>
        {refreshing ? <span className="ml-2 opacity-60">Updating…</span> : null}
      </p>
      <div
        className="flex flex-wrap gap-1"
        role="group"
        aria-label="Summary period"
      >
        {REPORT_PERIODS.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onChange(p)}
            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
              period === p
                ? 'bg-blue-600 text-white shadow-sm'
                : 'bg-slate-100 text-slate-700 ring-1 ring-slate-200 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-600 dark:hover:bg-slate-700'
            }`}
          >
            {REPORT_PERIOD_LABELS[p] || p}
          </button>
        ))}
      </div>
    </div>
  );
};

export default ReportSummaryPeriodToggle;
