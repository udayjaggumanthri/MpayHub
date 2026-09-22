import React, { useEffect, useState } from 'react';
import { FiArrowDown, FiArrowUp, FiBarChart2 } from 'react-icons/fi';
import { reportsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';

const INTERVALS = [
  { value: 'daily', label: 'Today' },
  { value: 'weekly', label: 'This week' },
  { value: 'monthly', label: 'This month' },
];

function ChangeBadge({ value }) {
  const n = Number(value || 0);
  const up = n >= 0;
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
        up
          ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
          : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
      }`}
    >
      {up ? <FiArrowUp aria-hidden /> : <FiArrowDown aria-hidden />}
      {Math.abs(n).toFixed(1)}%
    </span>
  );
}

const Metric = ({ label, value, change, icon: Icon, tone }) => (
  <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/50">
    <div className="flex items-center justify-between gap-2">
      <span className={`inline-flex h-8 w-8 items-center justify-center rounded-lg ${tone}`}>
        <Icon className="h-4 w-4" aria-hidden />
      </span>
      <ChangeBadge value={change} />
    </div>
    <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
      {label}
    </p>
    <p className="mt-0.5 text-xl font-bold tabular-nums text-slate-900 dark:text-slate-100">{value}</p>
    <p className="mt-0.5 text-[11px] text-slate-400">vs. previous period</p>
  </div>
);

const TodaysSummaryWidget = () => {
  const [interval, setIntervalValue] = useState('daily');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    reportsAPI.getDashboardTodaysSummary({ interval }).then((res) => {
      if (!mounted) return;
      setData(res.success ? res.data : null);
      setLoading(false);
    });
    return () => {
      mounted = false;
    };
  }, [interval]);

  return (
    <section
      aria-labelledby="dash-summary-heading"
      className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm dark:border-slate-700/90 dark:bg-slate-900 sm:p-5"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2
          id="dash-summary-heading"
          className="text-[12px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400"
        >
          Today&apos;s Summary
        </h2>
        <select
          value={interval}
          onChange={(e) => setIntervalValue(e.target.value)}
          className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          aria-label="Summary period"
        >
          {INTERVALS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {loading && !data ? (
        <div className="space-y-3" aria-busy="true">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          <Metric
            label="Total Credits"
            value={formatCurrency(parseFloat(data?.total_credits || 0))}
            change={data?.credits_change_pct}
            icon={FiArrowUp}
            tone="bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
          />
          <Metric
            label="Total Debits"
            value={formatCurrency(parseFloat(data?.total_debits || 0))}
            change={data?.debits_change_pct}
            icon={FiArrowDown}
            tone="bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
          />
          <Metric
            label="Total Transactions"
            value={data?.transaction_count ?? 0}
            change={data?.count_change_pct}
            icon={FiBarChart2}
            tone="bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
          />
        </div>
      )}
    </section>
  );
};

export default TodaysSummaryWidget;
