import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FaCircleCheck, FaClock, FaCircleXmark } from 'react-icons/fa6';
import { reportsAPI } from '../../services/api';
import {
  buildAllModulesDrillDownUrl,
  buildModuleReportDrillDownUrl,
  drillDownAriaLabel,
  modulesWithStatusCount,
} from '../../utils/dashboardDrillDown';
import Card from '../common/Card';
import ReportDateRange from '../common/ReportDateRange';
import { todayIsoDate } from '../../utils/reportDate';


function firstOfMonthIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

function firstOfYearIso() {
  const y = new Date().getFullYear();
  return `${y}-01-01`;
}

function defaultDatesForInterval(interval) {
  const today = todayIsoDate();
  if (interval === 'monthly') return { dateFrom: firstOfMonthIso(), dateTo: today };
  if (interval === 'yearly') return { dateFrom: firstOfYearIso(), dateTo: today };
  return { dateFrom: today, dateTo: today };
}

function formatPeriodLabel(from, to) {
  if (!from || !to) return '';
  const fmt = (iso) =>
    new Date(`${iso}T12:00:00`).toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  if (from === to) return fmt(from);
  return `${fmt(from)} – ${fmt(to)}`;
}

const MODULE_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'payin', label: 'Pay-in' },
  { value: 'payout', label: 'Payout' },
  { value: 'bbps', label: 'BBPS' },
];

const INTERVAL_OPTIONS = [
  { value: 'daily', label: 'Today' },
  { value: 'monthly', label: 'MTD' },
  { value: 'yearly', label: 'YTD' },
];

const MODULE_LABELS = {
  payin: 'Pay-in',
  payout: 'Payout',
  bbps: 'BBPS',
};

const selectClass =
  'rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2 py-1 text-xs font-medium text-slate-800 dark:text-slate-200 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400';

/**
 * @param {{ variant?: 'compact' | 'full' }} props
 * compact — embedded in welcome hero (top-right); full — standalone section (legacy)
 */
const DashboardTransactionStatus = ({ variant = 'compact' }) => {
  const navigate = useNavigate();
  const isCompact = variant === 'compact';

  const [filters, setFilters] = useState(() => ({
    module: 'all',
    interval: 'daily',
    ...defaultDatesForInterval('daily'),
  }));
  const [appliedQuery, setAppliedQuery] = useState(() => ({
    module: 'all',
    interval: 'daily',
    ...defaultDatesForInterval('daily'),
  }));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);
  const [showDates, setShowDates] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const params = {
      module: appliedQuery.module,
      interval: appliedQuery.interval,
      date_from: appliedQuery.dateFrom,
      date_to: appliedQuery.dateTo,
    };
    const res = await reportsAPI.getDashboardTransactionStatusCounts(params);
    if (res.success && res.data) {
      setData(res.data);
    } else {
      setData(null);
      setError(res.message || 'Could not load counts');
    }
    setLoading(false);
  }, [appliedQuery]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const onFocus = () => load();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [load]);

  const counts = data?.counts || { PENDING: 0, SUCCESS: 0, FAILED: 0, total: 0 };
  const byModule = data?.by_module;
  const periodLabel = useMemo(
    () => formatPeriodLabel(data?.period?.from, data?.period?.to),
    [data?.period]
  );

  const handleIntervalChange = (interval) => {
    const dates = defaultDatesForInterval(interval);
    setFilters((f) => ({
      ...f,
      interval,
      ...dates,
    }));
    setAppliedQuery((q) => ({
      ...q,
      interval,
      ...dates,
    }));
  };

  const drillDownContext = useMemo(
    () => ({
      dateFrom: appliedQuery.dateFrom,
      dateTo: appliedQuery.dateTo,
      periodLabel,
    }),
    [appliedQuery.dateFrom, appliedQuery.dateTo, periodLabel]
  );

  const navigateDrillDown = useCallback(
    (moduleKey, statusKey) => {
      const count =
        moduleKey && byModule?.[moduleKey]
          ? byModule[moduleKey][statusKey] ?? 0
          : counts[statusKey] ?? 0;
      if (!count || count <= 0) return;

      const url =
        moduleKey && moduleKey !== 'all'
          ? buildModuleReportDrillDownUrl({
              module: moduleKey,
              status: statusKey,
              dateFrom: drillDownContext.dateFrom,
              dateTo: drillDownContext.dateTo,
            })
          : filters.module !== 'all'
            ? buildModuleReportDrillDownUrl({
                module: filters.module,
                status: statusKey,
                dateFrom: drillDownContext.dateFrom,
                dateTo: drillDownContext.dateTo,
              })
            : (() => {
                const hits = modulesWithStatusCount(byModule, statusKey);
                if (hits.length === 1) {
                  return buildModuleReportDrillDownUrl({
                    module: hits[0],
                    status: statusKey,
                    dateFrom: drillDownContext.dateFrom,
                    dateTo: drillDownContext.dateTo,
                  });
                }
                return buildAllModulesDrillDownUrl({
                  status: statusKey,
                  dateFrom: drillDownContext.dateFrom,
                  dateTo: drillDownContext.dateTo,
                });
              })();
      navigate(url);
    },
    [byModule, counts, drillDownContext, filters.module, navigate]
  );

  const statusTiles = [
    {
      key: 'PENDING',
      label: 'Pending',
      short: 'P',
      value: counts.PENDING ?? 0,
      icon: FaClock,
      ring: 'ring-amber-200/80 dark:ring-amber-800/80',
      bg: 'bg-amber-50 dark:bg-amber-950/40',
      accent: 'text-amber-900 dark:text-amber-300',
      dot: 'bg-amber-500',
    },
    {
      key: 'SUCCESS',
      label: 'Success',
      short: 'S',
      value: counts.SUCCESS ?? 0,
      icon: FaCircleCheck,
      ring: 'ring-emerald-200/80 dark:ring-emerald-800/80',
      bg: 'bg-emerald-50 dark:bg-emerald-950/40',
      accent: 'text-emerald-900 dark:text-emerald-300',
      dot: 'bg-emerald-500',
    },
    {
      key: 'FAILED',
      label: 'Failed',
      short: 'F',
      value: counts.FAILED ?? 0,
      icon: FaCircleXmark,
      ring: 'ring-red-200/80 dark:ring-red-800/80',
      bg: 'bg-red-50 dark:bg-red-950/40',
      accent: 'text-red-900 dark:text-red-300',
      dot: 'bg-red-500',
    },
  ];

  const filterBar = (
    <div className={`flex flex-wrap items-center gap-1.5 ${isCompact ? '' : 'mb-6 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50 p-4 gap-3'}`}>
      <select
        value={filters.module}
        onChange={(e) => {
          const module = e.target.value;
          setFilters((f) => ({ ...f, module }));
          setAppliedQuery((q) => ({ ...q, module }));
        }}
        className={isCompact ? selectClass : 'min-w-[160px] rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2.5 text-sm font-medium text-slate-800 dark:text-slate-200 shadow-sm'}
        aria-label="Module"
      >
        {MODULE_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {isCompact ? o.label : (o.value === 'all' ? 'All modules' : o.label)}
          </option>
        ))}
      </select>
      <select
        value={filters.interval}
        onChange={(e) => handleIntervalChange(e.target.value)}
        className={isCompact ? selectClass : 'min-w-[130px] rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2.5 text-sm font-medium text-slate-800 dark:text-slate-200 shadow-sm'}
        aria-label="Period"
      >
        {INTERVAL_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {isCompact ? (
        <button
          type="button"
          onClick={() => setShowDates((v) => !v)}
          className="rounded-md px-2 py-1 text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-white dark:hover:bg-slate-900 hover:text-slate-900 dark:hover:text-slate-100"
          aria-expanded={showDates}
        >
          {showDates ? 'Hide dates' : 'Dates'}
        </button>
      ) : (
        <div className="min-w-0 w-full sm:w-auto sm:min-w-[280px]">
          <ReportDateRange
            idPrefix="dash-status"
            compact
            showApply
            applyLabel="Apply"
            fromLabel=""
            toLabel=""
            dateFrom={filters.dateFrom}
            dateTo={filters.dateTo}
            onChange={({ dateFrom, dateTo }) =>
              setFilters((f) => ({ ...f, dateFrom, dateTo }))
            }
            onApply={({ dateFrom, dateTo }) =>
              setAppliedQuery((q) => ({ ...q, dateFrom, dateTo }))
            }
          />
        </div>
      )}
    </div>
  );

  const dateRow =
    isCompact && showDates ? (
      <div className="mt-2 min-w-0">
        <ReportDateRange
          idPrefix="dash-status-compact"
          compact
          showApply
          applyLabel="Apply"
          fromLabel=""
          toLabel=""
          dateFrom={filters.dateFrom}
          dateTo={filters.dateTo}
          onChange={({ dateFrom, dateTo }) =>
            setFilters((f) => ({ ...f, dateFrom, dateTo }))
          }
          onApply={({ dateFrom, dateTo }) =>
            setAppliedQuery((q) => ({ ...q, dateFrom, dateTo }))
          }
        />
      </div>
    ) : null;

  const statusGrid = (
    <div className={isCompact ? 'grid grid-cols-3 gap-2' : 'grid grid-cols-1 gap-4 sm:grid-cols-3'}>
      {statusTiles.map((c) => {
        const Icon = c.icon;
        const countNum = Number(c.value) || 0;
        const canDrill = !loading && countNum > 0;
        const moduleForTile = filters.module !== 'all' ? filters.module : null;
        const tileLabel = drillDownAriaLabel({
          moduleLabel: moduleForTile ? MODULE_LABELS[moduleForTile] : '',
          status: c.label,
          count: countNum,
          periodLabel: drillDownContext.periodLabel,
        });

        if (isCompact) {
          const inner = (
            <>
              <div className="flex items-center justify-between gap-1">
                <span className={`text-[10px] font-semibold uppercase tracking-wide ${c.accent}`}>
                  {c.label}
                </span>
                <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} aria-hidden />
              </div>
              <p className={`mt-0.5 text-xl font-bold tabular-nums leading-none ${c.accent}`}>
                {loading ? '—' : countNum.toLocaleString('en-IN')}
              </p>
            </>
          );
          return (
            <div
              key={c.key}
              className={`rounded-lg border border-slate-200/90 dark:border-slate-700/90 ${c.bg} px-2.5 py-2.5 ring-1 ${c.ring}`}
            >
              {canDrill ? (
                <button
                  type="button"
                  onClick={() => navigateDrillDown(moduleForTile, c.key)}
                  className={`w-full text-left rounded-md transition hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${canDrill ? 'cursor-pointer' : ''}`}
                  aria-label={tileLabel}
                >
                  {inner}
                </button>
              ) : (
                inner
              )}
            </div>
          );
        }
        return (
          <div key={c.key} className={`rounded-xl border p-5 shadow-sm ${c.ring} ${c.bg}`}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">{c.label}</p>
                {canDrill ? (
                  <button
                    type="button"
                    onClick={() => navigateDrillDown(moduleForTile, c.key)}
                    className={`mt-2 text-3xl font-bold tabular-nums ${c.accent} hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded`}
                    aria-label={tileLabel}
                  >
                    {countNum.toLocaleString('en-IN')}
                  </button>
                ) : (
                  <p className={`mt-2 text-3xl font-bold tabular-nums ${c.accent}`}>
                    {countNum.toLocaleString('en-IN')}
                  </p>
                )}
              </div>
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/80 dark:bg-slate-900/80">
                <Icon size={22} className={c.accent} />
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );

  const moduleBreakdown =
    filters.module === 'all' && byModule ? (
      <div
        className={
          isCompact
            ? 'mt-2 flex flex-wrap gap-1'
            : 'mt-6 flex flex-wrap gap-2 border-t border-slate-100 dark:border-slate-800 pt-4'
        }
      >
        {Object.entries(byModule).map(([key, row]) => {
          const statuses = [
            { key: 'PENDING', value: row.PENDING ?? 0, className: 'text-amber-700 dark:text-amber-300' },
            { key: 'SUCCESS', value: row.SUCCESS ?? 0, className: 'text-emerald-700 dark:text-emerald-300' },
            { key: 'FAILED', value: row.FAILED ?? 0, className: 'text-red-700 dark:text-red-300' },
          ];
          return (
            <span
              key={key}
              className={
                isCompact
                  ? 'inline-flex items-center gap-1 rounded-md bg-white/90 dark:bg-slate-900/90 px-2 py-0.5 text-[10px] text-slate-600 dark:text-slate-400 ring-1 ring-slate-200/80 dark:ring-slate-700/80'
                  : 'rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-700 dark:text-slate-300'
              }
            >
              <span className="font-semibold text-slate-800 dark:text-slate-200">{MODULE_LABELS[key] || key}</span>
              {statuses.map((st, idx) => (
                <React.Fragment key={st.key}>
                  {idx > 0 ? <span className="text-slate-300">/</span> : null}
                  {st.value > 0 && !loading ? (
                    <button
                      type="button"
                      onClick={() => navigateDrillDown(key, st.key)}
                      className={`font-semibold tabular-nums hover:underline focus:outline-none focus-visible:ring-1 focus-visible:ring-blue-500 rounded ${st.className}`}
                      aria-label={drillDownAriaLabel({
                        moduleLabel: MODULE_LABELS[key] || key,
                        status: st.key,
                        count: st.value,
                        periodLabel: drillDownContext.periodLabel,
                      })}
                    >
                      {st.value}
                    </button>
                  ) : (
                    <span className={st.className}>{st.value}</span>
                  )}
                </React.Fragment>
              ))}
            </span>
          );
        })}
      </div>
    ) : null;

  const footer =
    periodLabel && !loading ? (
      <p className={isCompact ? 'mt-2 text-[10px] leading-snug text-slate-500 dark:text-slate-400' : 'mt-4 text-xs text-slate-500 dark:text-slate-400'}>
        {periodLabel}
        <span className="text-slate-300"> · </span>
        {(counts.total ?? 0).toLocaleString('en-IN')} total
        <span className="text-slate-300"> · </span>
        IST
      </p>
    ) : null;

  if (isCompact) {
    return (
      <div
        className="w-full rounded-xl border border-slate-200/90 dark:border-slate-700/90 bg-gradient-to-br from-slate-50/90 dark:from-slate-900/90 to-white dark:to-slate-900 p-3.5 shadow-sm sm:p-4"
        aria-label="Portal transaction status"
      >
        <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Portal activity</p>
          {filterBar}
        </div>
        {dateRow}
        {error && (
          <p className="mb-2 text-xs text-red-700 dark:text-red-300" role="alert">
            {error}
          </p>
        )}
        {statusGrid}
        {moduleBreakdown}
        {footer}
      </div>
    );
  }

  return (
    <section aria-labelledby="dash-txn-status-heading" className="space-y-4">
      <div className="flex flex-col gap-1 border-b border-slate-100 dark:border-slate-800 pb-4">
        <h2 id="dash-txn-status-heading" className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Transaction status overview
        </h2>
      </div>
      <Card className="border border-slate-200/90 dark:border-slate-700/90 shadow-sm" padding="lg">
        {filterBar}
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 px-4 py-3 text-sm text-red-800 dark:text-red-300">
            {error}
          </div>
        )}
        {loading ? (
          <div className="py-12 text-center text-sm text-slate-500 dark:text-slate-400">Loading…</div>
        ) : (
          <>
            {statusGrid}
            {moduleBreakdown}
            {footer}
          </>
        )}
      </Card>
    </section>
  );
};

export default DashboardTransactionStatus;
