import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { FiDownload, FiExternalLink } from 'react-icons/fi';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { reportsAPI } from '../../services/api';
import { isAdminUser } from '../../utils/rolePermissions';
import {
  buildUnderlyingTxnReportUrl,
  canOpenUnderlyingReport,
  canPrintUnderlyingReceipt,
} from '../../utils/reportDeepLink';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import ReportDateRange from '../common/ReportDateRange';
import ReportPagination from '../common/ReportPagination';
import Button from '../common/Button';
import { countActiveReportFilters } from '../../utils/reportFilters';
import {
  CollapsibleReportFilters,
  FILTER_INPUT_CLASS,
  FILTER_SELECT_CLASS,
  ReportFilterDateRow,
  ReportFilterField,
  ReportFilterGrid,
} from '../common/ReportFilterPanel';

const DEFAULT_PAGE_SIZE = 25;

const EMPTY_FILTERS = {
  dateFrom: '',
  dateTo: '',
  mobile: '',
  agentRole: '',
  serviceId: '',
  module: '',
};

const MODULE_OPTIONS = [
  { value: '', label: 'All modules' },
  { value: 'payin', label: 'Pay-in / QR / Gateway' },
  { value: 'bbps', label: 'BBPS' },
  { value: 'payout', label: 'Payout' },
  { value: 'bank_verification', label: 'Bank verify' },
  { value: 'aeps', label: 'AEPS' },
  { value: 'cms', label: 'CMS' },
];

const moduleLabel = (mod) => {
  const key = String(mod || '').toLowerCase();
  const hit = MODULE_OPTIONS.find((m) => m.value === key);
  if (hit) return hit.label;
  if (!key || key === '—') return '—';
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
};

/**
 * Admin / Super Admin — platform service fees tracked separately from commission.
 */
const ServiceFeeTracker = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const allowed = isAdminUser(user);
  const userId = user?.id ?? user?.user_id;
  const fetchIdRef = useRef(0);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const hasLoadedOnceRef = useRef(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState(null);
  const initialFromUrl = useMemo(() => {
    const dateFrom = (searchParams.get('date_from') || '').trim();
    const dateTo = (searchParams.get('date_to') || '').trim();
    const serviceId = (searchParams.get('service_id') || '').trim();
    const module = (searchParams.get('module') || '').trim();
    if (!dateFrom && !dateTo && !serviceId && !module) return EMPTY_FILTERS;
    return { ...EMPTY_FILTERS, dateFrom, dateTo, serviceId, module };
  }, [searchParams]);
  const [filters, setFilters] = useState(initialFromUrl);
  const [appliedFilters, setAppliedFilters] = useState(initialFromUrl);
  const [showFilters, setShowFilters] = useState(
    () =>
      Boolean(
        initialFromUrl.dateFrom ||
          initialFromUrl.dateTo ||
          initialFromUrl.serviceId ||
          initialFromUrl.module
      )
  );
  const [exportBusy, setExportBusy] = useState(false);

  const buildParams = useCallback(
    (extra = {}) => {
      const params = { ...extra };
      if (appliedFilters.dateFrom) params.date_from = appliedFilters.dateFrom;
      if (appliedFilters.dateTo) params.date_to = appliedFilters.dateTo;
      if (appliedFilters.mobile.trim()) params.mobile = appliedFilters.mobile.trim();
      if (appliedFilters.agentRole.trim()) params.agent_role = appliedFilters.agentRole.trim();
      if (appliedFilters.serviceId.trim()) params.service_id = appliedFilters.serviceId.trim();
      if (appliedFilters.module) params.module = appliedFilters.module;
      return params;
    },
    [appliedFilters]
  );

  /** Summary tiles ignore module chip so all modules stay visible while filtering the table. */
  const buildSummaryParams = useCallback(() => {
    const params = {};
    if (appliedFilters.dateFrom) params.date_from = appliedFilters.dateFrom;
    if (appliedFilters.dateTo) params.date_to = appliedFilters.dateTo;
    if (appliedFilters.mobile.trim()) params.mobile = appliedFilters.mobile.trim();
    if (appliedFilters.agentRole.trim()) params.agent_role = appliedFilters.agentRole.trim();
    if (appliedFilters.serviceId.trim()) params.service_id = appliedFilters.serviceId.trim();
    return params;
  }, [appliedFilters]);

  const loadReport = useCallback(async () => {
    if (!userId || !allowed) return;

    const runId = ++fetchIdRef.current;
    if (hasLoadedOnceRef.current) setIsRefreshing(true);
    else setLoading(true);

    try {
      const listParams = buildParams({ page, page_size: pageSize });
      const summaryParams = buildSummaryParams();

      const [summaryRes, listRes] = await Promise.all([
        reportsAPI.getServiceFeeSummary(summaryParams),
        reportsAPI.getServiceFeeReport(listParams),
      ]);

      if (runId !== fetchIdRef.current) return;

      setSummary(summaryRes.success ? summaryRes.data || null : null);

      if (!listRes.success) {
        setRows([]);
        setTotal(0);
        return;
      }

      setTotal(Number(listRes.data?.total) || 0);
      const rawLedger = listRes.data?.ledger || [];
      setRows(
        rawLedger.map((row) => {
          const m = row.meta || {};
          return {
            id: `fee-${row.id}`,
            date: row.created_at,
            reference: row.reference_service_id || '—',
            module: row.module || row.source || '—',
            fromUser: row.source_name_snapshot || m.source_name || '—',
            fromRole: row.source_role || m.source_role || '—',
            customerCharge: parseFloat(row.customer_charge) || 0,
            feeAmount: parseFloat(row.amount) || 0,
            sliceDisplay: row.slice_display || row.slice_key || m.slice || '',
          };
        })
      );
    } catch (error) {
      if (runId !== fetchIdRef.current) return;
      console.error('Error loading service fee tracker:', error);
      setRows([]);
      setTotal(0);
      setSummary(null);
    } finally {
      if (runId !== fetchIdRef.current) return;
      setLoading(false);
      setIsRefreshing(false);
      if (!hasLoadedOnceRef.current) {
        hasLoadedOnceRef.current = true;
        setHasLoadedOnce(true);
      }
    }
  }, [userId, allowed, buildParams, buildSummaryParams, page, pageSize]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const exportCsv = async () => {
    setExportBusy(true);
    try {
      const res = await reportsAPI.downloadReportCsv(
        '/reports/service-fees/export.csv',
        buildParams({ page: 1, page_size: 10000 })
      );
      if (!res.success || !res.blob) return;
      const url = window.URL.createObjectURL(res.blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'service_fee_tracker.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } finally {
      setExportBusy(false);
    }
  };

  const moduleBreakdown = useMemo(() => {
    const bm = summary?.by_module || {};
    return Object.entries(bm)
      .map(([mod, info]) => ({
        key: String(mod || '').toLowerCase(),
        label: moduleLabel(mod),
        total: parseFloat(info?.total) || 0,
        count: Number(info?.count) || 0,
      }))
      .filter((m) => m.count > 0 || m.total > 0)
      .sort((a, b) => b.total - a.total || a.label.localeCompare(b.label));
  }, [summary]);

  const totalFees =
    summary?.service_fees != null ? parseFloat(summary.service_fees) || 0 : null;

  const selectModule = (moduleKey) => {
    const next = moduleKey === appliedFilters.module ? '' : moduleKey;
    const nextFilters = { ...filters, module: next };
    setFilters(nextFilters);
    setAppliedFilters(nextFilters);
    setPage(1);
  };

  if (!allowed) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-6 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
        Service Fee Tracker is available to Admin and Super Admin only.
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-4">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 sm:text-2xl">
            Service Fee Tracker
          </h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Payout and bank-verify charges paid to gateways — tracked here only, not
            credited to Admin Main. Pay In leftover and BBPS extra appear on the
            Commission report as platform profit.
          </p>
        </div>
        <Button
          size="sm"
          variant="secondary"
          loading={exportBusy}
          onClick={exportCsv}
          className="shrink-0 self-start sm:self-auto"
        >
          <FiDownload className="mr-1.5 inline h-4 w-4" aria-hidden />
          Download CSV
        </Button>
      </header>

      <CollapsibleReportFilters
        open={showFilters}
        onOpenChange={setShowFilters}
        activeCount={countActiveReportFilters(appliedFilters)}
        applying={isRefreshing}
        onApply={() => {
          setPage(1);
          setAppliedFilters({ ...filters });
        }}
        onClear={() => {
          setFilters({ ...EMPTY_FILTERS });
          setAppliedFilters({ ...EMPTY_FILTERS });
          setPage(1);
        }}
      >
        <ReportFilterGrid>
          <ReportFilterField label="Service ID" htmlFor="sft-service-id">
            <input
              id="sft-service-id"
              type="text"
              value={filters.serviceId}
              onChange={(e) => setFilters({ ...filters, serviceId: e.target.value })}
              placeholder="Transaction / service ID"
              className={FILTER_INPUT_CLASS}
            />
          </ReportFilterField>
          <ReportFilterField label="Module" htmlFor="sft-module">
            <select
              id="sft-module"
              value={filters.module}
              onChange={(e) => setFilters({ ...filters, module: e.target.value })}
              className={FILTER_SELECT_CLASS}
            >
              {MODULE_OPTIONS.map((o) => (
                <option key={o.value || 'all'} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </ReportFilterField>
          <ReportFilterField label="Source mobile" htmlFor="sft-mobile">
            <input
              id="sft-mobile"
              type="text"
              inputMode="tel"
              value={filters.mobile}
              onChange={(e) => setFilters({ ...filters, mobile: e.target.value })}
              placeholder="Agent mobile"
              className={FILTER_INPUT_CLASS}
            />
          </ReportFilterField>
          <ReportFilterField label="Source role" htmlFor="sft-role">
            <input
              id="sft-role"
              type="text"
              value={filters.agentRole}
              onChange={(e) => setFilters({ ...filters, agentRole: e.target.value })}
              placeholder="e.g. Retailer"
              className={FILTER_INPUT_CLASS}
            />
          </ReportFilterField>
        </ReportFilterGrid>
        <ReportFilterDateRow>
          <ReportDateRange
            idPrefix="sft"
            dateFrom={filters.dateFrom}
            dateTo={filters.dateTo}
            fromLabel="Date from"
            toLabel="Date to"
            compact
            onChange={({ dateFrom, dateTo }) =>
              setFilters((prev) => ({ ...prev, dateFrom, dateTo }))
            }
          />
        </ReportFilterDateRow>
      </CollapsibleReportFilters>

      <div
        className={`rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900 sm:px-5 sm:py-4 ${
          isRefreshing && hasLoadedOnce ? 'opacity-70' : ''
        }`}
      >
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Total service fees
        </p>
        <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100 sm:text-3xl">
          {totalFees != null ? formatCurrency(totalFees) : loading ? '…' : '—'}
        </p>
      </div>

      {moduleBreakdown.length > 0 ? (
        <div
          className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5"
          role="group"
          aria-label="Fees by module"
        >
          <button
            type="button"
            onClick={() => selectModule('')}
            className={`min-h-[72px] rounded-xl border px-3 py-2.5 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
              !appliedFilters.module
                ? 'border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-950/40'
                : 'border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600'
            }`}
          >
            <p className="text-xs font-semibold text-slate-800 dark:text-slate-100">All modules</p>
            <p className="mt-1 text-sm font-bold tabular-nums text-slate-900 dark:text-slate-100">
              {totalFees != null ? formatCurrency(totalFees) : '—'}
            </p>
            <p className="mt-0.5 text-[11px] tabular-nums text-slate-500 dark:text-slate-400">
              {moduleBreakdown.reduce((s, m) => s + m.count, 0)} entries
            </p>
          </button>
          {moduleBreakdown.map((m) => {
            const active = appliedFilters.module === m.key;
            return (
              <button
                type="button"
                key={m.key}
                onClick={() => selectModule(m.key)}
                aria-pressed={active}
                className={`min-h-[72px] rounded-xl border px-3 py-2.5 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  active
                    ? 'border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-950/40'
                    : 'border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600'
                }`}
              >
                <p className="truncate text-xs font-semibold text-slate-800 dark:text-slate-100">
                  {m.label}
                </p>
                <p className="mt-1 text-sm font-bold tabular-nums text-slate-900 dark:text-slate-100">
                  {formatCurrency(m.total)}
                </p>
                <p className="mt-0.5 text-[11px] tabular-nums text-slate-500 dark:text-slate-400">
                  {m.count} {m.count === 1 ? 'entry' : 'entries'}
                </p>
              </button>
            );
          })}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
        {loading && !hasLoadedOnce ? (
          <div className="py-12 text-center text-sm text-slate-500">Loading…</div>
        ) : hasLoadedOnce && rows.length === 0 && !isRefreshing ? (
          <div className="py-12 text-center text-sm text-slate-500">No service fee records found</div>
        ) : (
          <div className={isRefreshing ? 'opacity-60 pointer-events-none' : ''}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse md:min-w-[900px]">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50 dark:border-slate-700 dark:bg-slate-800/50">
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                      Date &amp; time
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                      Reference
                    </th>
                    <th className="hidden px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300 sm:table-cell">
                      Module
                    </th>
                    <th className="hidden px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300 lg:table-cell">
                      Slice
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                      Source user
                    </th>
                    <th className="hidden px-3 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300 md:table-cell">
                      Customer charge
                    </th>
                    <th className="px-3 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                      Service fee
                    </th>
                    <th className="hidden px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300 sm:table-cell">
                      Status
                    </th>
                    <th className="px-3 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                      Open
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const openUrl = canOpenUnderlyingReport(row.module)
                      ? buildUnderlyingTxnReportUrl({
                          module: row.module,
                          serviceId: row.reference,
                          platformScope: true,
                          openReceipt: canPrintUnderlyingReceipt(row.module),
                        })
                      : null;
                    return (
                      <tr
                        key={row.id}
                        className="border-b border-gray-200 hover:bg-gray-50 dark:border-slate-700 dark:hover:bg-slate-800"
                      >
                        <td className="whitespace-nowrap px-3 py-2.5 text-sm text-gray-700 dark:text-slate-300">
                          {formatDateTime(row.date)}
                        </td>
                        <td className="max-w-[140px] truncate px-3 py-2.5 font-mono text-xs text-gray-900 dark:text-slate-100 sm:max-w-none">
                          {row.reference}
                        </td>
                        <td className="hidden px-3 py-2.5 text-sm text-gray-800 dark:text-slate-200 sm:table-cell">
                          {moduleLabel(row.module)}
                        </td>
                        <td className="hidden px-3 py-2.5 text-sm text-gray-600 dark:text-slate-400 lg:table-cell">
                          {row.sliceDisplay || '—'}
                        </td>
                        <td className="px-3 py-2.5 text-sm text-gray-700 dark:text-slate-300">
                          <div className="truncate">{row.fromUser}</div>
                          {row.fromRole && row.fromRole !== '—' ? (
                            <div className="text-xs text-slate-500">{row.fromRole}</div>
                          ) : null}
                          <div className="mt-0.5 text-[11px] text-slate-500 sm:hidden">
                            {moduleLabel(row.module)}
                          </div>
                        </td>
                        <td className="hidden px-3 py-2.5 text-right text-sm tabular-nums text-gray-800 dark:text-slate-200 md:table-cell">
                          {row.customerCharge > 0 ? formatCurrency(row.customerCharge) : '—'}
                        </td>
                        <td className="px-3 py-2.5 text-right text-sm font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                          {formatCurrency(row.feeAmount)}
                        </td>
                        <td className="hidden px-3 py-2.5 text-sm sm:table-cell">
                          <span className="inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-bold uppercase text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200">
                            Tracked
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          {openUrl ? (
                            <button
                              type="button"
                              onClick={() => navigate(openUrl)}
                              className="inline-flex min-h-[36px] items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50 dark:text-blue-300 dark:hover:bg-blue-950/40"
                              title="Open underlying transaction"
                            >
                              <FiExternalLink className="h-3.5 w-3.5" />
                              Txn
                            </button>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="border-t border-slate-200 px-2 py-2 dark:border-slate-700 sm:px-3">
              <ReportPagination
                page={page}
                pageSize={pageSize}
                total={total}
                loading={isRefreshing}
                onPageChange={setPage}
                onPageSizeChange={(size) => {
                  setPageSize(size);
                  setPage(1);
                }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ServiceFeeTracker;
